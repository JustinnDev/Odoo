from odoo import api, fields, models

class ReceptionPriceListLine(models.Model):
    _name = 'reception.price.list.line'
    _description = 'Lista de Precios'
    _order = 'product_id'

    product_id = fields.Many2one(
        'product.product', string='Producto', required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        default=lambda self: self.env.company.currency_id, readonly=True)
    price_1 = fields.Float(string='USDT', digits='Product Price', default=0.0)
    price_2 = fields.Float(string='Efectivo', digits='Product Price', default=0.0)
    price_3 = fields.Float(string='Jarlis USDT', digits='Product Price', default=0.0)
    price_4 = fields.Float(string='Jarlis $$$', digits='Product Price', default=0.0)
    price_5 = fields.Float(string='Ortega USDT', digits='Product Price', default=0.0)
    price_6 = fields.Float(string='Ortega $$$', digits='Product Price', default=0.0)
    price_7 = fields.Float(string='Alfonzo USDT', digits='Product Price', default=0.0)
    price_8 = fields.Float(string='Alfonzo $$$', digits='Product Price', default=0.0)
    price_9 = fields.Float(string='Yulianis', digits='Product Price', default=0.0)
    price_10 = fields.Float(string='Precio 10', digits='Product Price', default=0.0)

    _sql_constraints = [
        ('product_uniq', 'unique(product_id)',
         'Este producto ya tiene una fila en la lista de precios.'),
    ]

    @api.model
    def _is_material_product(self, product):
        """Devuelve True si el producto se puede vender."""
        return bool(product.sale_ok)

    @api.model
    def _ensure_lines(self, products):
        """Crea líneas de lista de precios solo para productos válidos."""
        #self._cleanup_invalid_lines()
        material_products = products.filtered(self._is_material_product)
        existing = self.search([]).mapped('product_id')
        to_create = [
            {'product_id': product.id}
            for product in material_products
            if product not in existing
        ]
        if to_create:
            self.create(to_create)

    @api.model
    def _cleanup_invalid_lines(self, products=None):
        """Elimina líneas cuyos productos ya no cumplen la condición."""
        domain = []
        if products is not None:
            domain = [('product_id', 'in', products.ids)]
        lines = self.search(domain)
        invalid = lines.filtered(
            lambda line: not self._is_material_product(line.product_id)
        )
        if invalid:
            invalid.unlink()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        PriceLine = self.env['reception.price.list.line']
        material_products = products.filtered(PriceLine._is_material_product)
        if material_products:
            PriceLine._ensure_lines(material_products)
        return products

    def write(self, vals):
        res = super().write(vals)
        # Disparar la sincronización cuando cambie cualquiera de estos campos
        if 'sale_ok' in vals or 'purchase_ok' in vals or 'categ_id' in vals:
            PriceLine = self.env['reception.price.list.line']

            # Crear líneas para productos válidos
            material_products = self.filtered(PriceLine._is_material_product)
            if material_products:
                PriceLine._ensure_lines(material_products)

            # Eliminar líneas de productos que ya no son válidos
            non_material = self - material_products
            if non_material:
                PriceLine.search([
                    ('product_id', 'in', non_material.ids)
                ]).unlink()

        return res