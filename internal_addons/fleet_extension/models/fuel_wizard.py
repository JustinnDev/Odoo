from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetExtensionFuelWizard(models.TransientModel):
    _name = 'fleet.extension.fuel.wizard'
    _description = 'Asistente de Operación de Combustible'

    tank_id = fields.Many2one(
        'fleet.extension.fuel_tank',
        string='Tanque',
        required=True,
    )
    operation_type = fields.Selection([
        ('refuel', 'Repostar'),
        ('consume', 'Consumir'),
        ('extract', 'Extraer'),
    ], string='Operación', required=True, default='refuel')
    product_id = fields.Many2one(
        'product.product',
        string='Producto de Combustible',
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Origen',
    )
    quantity = fields.Float(
        string='Cantidad',
        required=True,
        digits='Product Unit of Measure',
    )
    current_fuel = fields.Float(
        string='Combustible Actual',
        related='tank_id.current_fuel',
        readonly=True,
    )
    new_fuel_level = fields.Float(
        string='Nuevo Nivel',
        compute='_compute_new_fuel_level',
        readonly=True,
        digits='Product Unit of Measure',
    )

    inventory_consumption = fields.Boolean(
        string='Consumo de Inventario',
        default=True,
        help = 'Indica si la operacion afectara la producto de inventario'               
    )

    @api.depends('quantity', 'operation_type', 'current_fuel')
    def _compute_new_fuel_level(self):
        for wizard in self:
            if wizard.operation_type == 'refuel':
                wizard.new_fuel_level = wizard.current_fuel + wizard.quantity
            elif wizard.operation_type in ['consume', 'extract']:
                wizard.new_fuel_level = wizard.current_fuel - wizard.quantity
            else:
                wizard.new_fuel_level = wizard.current_fuel

    def action_confirm(self):
        """Ejecuta la operación de combustible."""
        self.ensure_one()
        if self.quantity <= 0:
            raise UserError(_('La cantidad debe ser positiva.'))

        if self.operation_type == 'refuel':
            self.tank_id.refuel(self.product_id, self.quantity, self.inventory_consumption)
        elif self.operation_type == 'consume':
            self.tank_id.consume(self.quantity)
        elif self.operation_type == 'extract':
            self.tank_id.extract(self.product_id, self.quantity, self.inventory_consumption)

        return {'type': 'ir.actions.act_window_close'}