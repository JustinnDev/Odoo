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
    price_3 = fields.Float(string='Jarlis', digits='Product Price', default=0.0)
    price_4 = fields.Float(string='Alfonzo', digits='Product Price', default=0.0)
    price_5 = fields.Float(string='Precio 5', digits='Product Price', default=0.0)
    price_6 = fields.Float(string='Precio 6', digits='Product Price', default=0.0)

    _sql_constraints = [
        ('product_uniq', 'unique(product_id)',
         'Este producto ya tiene una fila en la lista de precios.'),
    ]

    @api.model
    def _ensure_lines(self, products):
        existing = self.search([]).mapped('product_id')
        to_create = [{'product_id': product.id} for product in products if product not in existing]
        if to_create:
            self.create(to_create)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        purchasable = products.filtered(lambda p: p.purchase_ok)
        if purchasable:
            self.env['reception.price.list.line']._ensure_lines(purchasable)
        return products

    def write(self, vals):
        res = super().write(vals)
        if vals.get('purchase_ok'):
            self.env['reception.price.list.line']._ensure_lines(
                self.filtered(lambda p: p.purchase_ok))
        return res
