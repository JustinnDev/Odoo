from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FleetExtensionFuelTank(models.Model):
    _name = 'fleet.extension.fuel_tank'
    _description = 'Tanque de Combustible Virtual'
    _rec_name = 'vehicle_id'

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehículo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    capacity = fields.Float(
        string='Capacidad',
        required=True,
        default=0.0,
        digits='Product Unit of Measure',
        help='Capacidad máxima del tanque en litros/galones.',
    )
    current_fuel = fields.Float(
        string='Combustible Actual',
        default=0.0,
        digits='Product Unit of Measure',
        help='Cantidad actual de combustible en el tanque.',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto de Combustible',
        required=True,
        help='Producto de inventario que se consume al repostar.',
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Origen',
        required=True,
        default=lambda self: self.env.ref('stock.stock_location_stock'),
        help='Ubicación de inventario desde donde se descuenta el combustible.',
    )

    @api.constrains('current_fuel', 'capacity')
    def _check_fuel_limits(self):
        for tank in self:
            if tank.current_fuel < 0:
                raise ValidationError(_('El combustible actual no puede ser negativo.'))
            if tank.current_fuel > tank.capacity:
                raise ValidationError(_('El combustible actual no puede superar la capacidad.'))

    def refuel(self, product, quantity):
        """Aumenta el combustible del tanque consumiendo producto del inventario."""
        self.ensure_one()
        if quantity <= 0:
            raise UserError(_('La cantidad a repostar debe ser positiva.'))
        if self.current_fuel + quantity > self.capacity:
            raise UserError(_('No se puede repostar por encima de la capacidad máxima.'))
        self._create_stock_move(product, quantity, 'out')
        self.current_fuel += quantity

    def consume(self, quantity):
        """Reduce el combustible del tanque sin afectar inventario."""
        self.ensure_one()
        if quantity <= 0:
            raise UserError(_('La cantidad a consumir debe ser positiva.'))
        if self.current_fuel - quantity < 0:
            raise UserError(_('No se puede consumir más combustible del disponible.'))
        self.current_fuel -= quantity

    def extract(self, product, quantity):
        """Extrae combustible del tanque y lo devuelve al inventario."""
        self.ensure_one()
        if quantity <= 0:
            raise UserError(_('La cantidad a extraer debe ser positiva.'))
        if self.current_fuel - quantity < 0:
            raise UserError(_('No se puede extraer más combustible del disponible.'))
        self._create_stock_move(product, quantity, 'in')
        self.current_fuel -= quantity

    def _create_stock_move(self, product, quantity, move_type):
        """Crea un movimiento de stock para consumo o devolución."""
        move_vals = {
            'name': f'Combustible {self.vehicle_id.name}',
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'location_id': self.source_location_id.id if move_type == 'out' else self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_stock').id if move_type == 'out' else self.source_location_id.id,
            'state': 'done',
            'date': fields.Datetime.now(),
        }
        self.env['stock.move'].create(move_vals)