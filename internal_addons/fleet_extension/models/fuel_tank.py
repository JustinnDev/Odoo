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
        readonly = True
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

    def action_refuel(self):
        """Abre el asistente para repostar combustible."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.extension.fuel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tank_id': self.id,
                'default_operation_type': 'refuel',
                'default_product_id': self.product_id.id,
                'default_source_location_id': self.source_location_id.id,
            },
        }

    def action_consume(self):
        """Abre el asistente para consumir combustible."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.extension.fuel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tank_id': self.id,
                'default_operation_type': 'consume',
            },
        }

    def action_extract(self):
        """Abre el asistente para extraer combustible."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.extension.fuel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tank_id': self.id,
                'default_operation_type': 'extract',
                'default_product_id': self.product_id.id,
                'default_source_location_id': self.source_location_id.id,
            },
        }

    def refuel(self, product, quantity, inventory_consumption):
        """Aumenta el combustible del tanque consumiendo producto del inventario."""
        self.ensure_one()
        if quantity <= 0:
            raise UserError(_('La cantidad a repostar debe ser positiva.'))
        if self.current_fuel + quantity > self.capacity:
            raise UserError(_('No se puede repostar por encima de la capacidad máxima.'))

        if inventory_consumption == True:
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

    def extract(self, product, quantity, inventory_consumption):
        """Extrae combustible del tanque y lo devuelve al inventario."""
        self.ensure_one()
        if quantity <= 0:
            raise UserError(_('La cantidad a extraer debe ser positiva.'))
        if self.current_fuel - quantity < 0:
            raise UserError(_('No se puede extraer más combustible del disponible.'))

        if inventory_consumption == True:
            self._create_stock_move(product, quantity, 'in')

        self.current_fuel -= quantity

    def _create_stock_move(self, product, quantity, move_type):
        """Crea un traslado interno para consumo o devolución de combustible."""
        self.ensure_one()
        
        # Obtener el tipo de picking interno
        picking_type = self.env.ref('stock.picking_type_internal')
        
        # Ubicación física de stock
        physical_location = self.env.ref('stock.stock_location_stock')
        
        # Determinar ubicaciones según el tipo de movimiento
        if move_type == 'out':
            # Consumo: de stock físico a ubicación de consumo
            source_location = physical_location
            dest_location = self.source_location_id
        else:
            # Extracción: de ubicación de consumo a stock físico
            source_location = self.source_location_id
            dest_location = physical_location
        
        # Crear el picking (traslado interno)
        picking_vals = {
            'origin': f'Fuel/{self.vehicle_id.name}',
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'move_ids': [(0, 0, {
                'name': f'Fuel {self.vehicle_id.name}',
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
            })],
        }
        picking = self.env['stock.picking'].create(picking_vals)

        if picking.name:
            picking.name = f'{picking.name}/{self.vehicle_id.name}'

        # Confirmar el picking
        picking.action_confirm()
        
        # Asignar cantidades
        picking.action_assign()
        
        # Establecer la cantidad realizada en las líneas de movimiento
        for move in picking.move_ids:
            if move.move_line_ids:
                for move_line in move.move_line_ids:
                    if move_line.quantity == 0:
                        move_line.quantity = move.product_uom_qty
            else:
                move.move_line_ids = [(0, 0, {
                    'product_id': move.product_id.id,
                    'quantity': move.product_uom_qty,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                })]
        
        # Validar el picking
        picking.button_validate()
        
        return picking