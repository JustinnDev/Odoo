from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PlantaProduction(models.Model):
    _name = 'planta.production'
    _description = 'Producción'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Procesada'),
        ('paid', 'Pagada'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)

    creator_ids = fields.Many2many(
        'hr.employee',
        string='Creadores',
        help='Empleados que participaron en la producción.',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        required=True,
        help='Contacto asociado a la producción para identificar el tipo.',
    )

    product_from_id = fields.Many2one(
        'product.product',
        string='Material de Origen',
        required=True,
        help='Material que se consume en la producción.',
    )
    product_to_id = fields.Many2one(
        'product.product',
        string='Material de Destino',
        required=True,
        help='Material que se produce.',
    )
    quantity = fields.Float(
        string='Cantidad',
        required=True,
        digits='Product Unit of Measure',
        help='Cantidad producida (kg).',
    )
    date = fields.Datetime(
        string='Fecha de Producción',
        required=True,
        default=fields.Datetime.now,
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Origen',
        required=True,
        default=lambda self: self.env.ref('stock.stock_location_stock'),
        help='Ubicación desde donde se descuenta el material de origen.',
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Destino',
        required=True,
        default=lambda self: self.env.ref('stock.stock_location_stock'),
        help='Ubicación donde se agrega el material producido.',
    )
    note = fields.Text(string='Notas')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('planta.production') or _('Nuevo')
        return super().create(vals_list)

    @api.constrains('quantity', 'product_from_id', 'product_to_id')
    def _check_production(self):
        for production in self:
            if production.quantity <= 0:
                raise ValidationError(_('La cantidad debe ser positiva.'))
            if production.product_from_id == production.product_to_id:
                raise ValidationError(_('El material de origen y destino no pueden ser iguales.'))

    def action_process(self):
        """
        Procesa la producción:
        - Descuenta material de origen del inventario
        - Agrega material de destino al inventario
        - Cambia el estado a 'done'
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede procesar una producción en borrador.'))
        if not self.creator_ids:
            raise UserError(_('Debe añadir al menos un creador.'))
        if self.quantity <= 0:
            raise UserError(_('La cantidad debe ser positiva.'))

        # Crear movimiento de salida del material de origen
        self._create_stock_move(
            product=self.product_from_id,
            quantity=self.quantity,
            move_type='out',
            source_location=self.source_location_id,
            dest_location=self.env.ref('stock.stock_location_inventory') if self.env.ref('stock.stock_location_inventory', raise_if_not_found=False) else self.source_location_id,
            partner=self.partner_id
        )

        # Crear movimiento de entrada del material de destino
        self._create_stock_move(
            product=self.product_to_id,
            quantity=self.quantity,
            move_type='in',
            source_location=self.env.ref('stock.stock_location_inventory') if self.env.ref('stock.stock_location_inventory', raise_if_not_found=False) else self.dest_location_id,
            dest_location=self.dest_location_id,
            partner=self.partner_id
        )

        # Descontar material de origen
        self.env['stock.quant']._update_available_quantity(
            self.product_from_id,
            self.source_location_id,
            -self.quantity,  # Negativo para descontar
        )

        # Agregar material de destino
        self.env['stock.quant']._update_available_quantity(
            self.product_to_id,
            self.dest_location_id,
            self.quantity,  # Positivo para agregar
        )

        self.write({
            'state': 'done',
            'date': self.date or fields.Datetime.now(),
        })

    def action_set_paid(self):
        """Marca la producción como pagada."""
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_('Solo se puede pagar una producción procesada.'))
        self.state = 'paid'

    def action_set_draft(self):
        """Vuelve a poner la producción en borrador."""
        self.ensure_one()
        if self.state not in ['done', 'cancel']:
            raise UserError(_('Solo se puede volver a borrador desde Procesada o Cancelada.'))
        self.state = 'draft'

    def action_cancel(self):
        """Cancela la producción."""
        self.ensure_one()
        if self.state not in ['draft', 'done']:
            raise UserError(_('Solo se puede cancelar una producción en borrador o procesada.'))
        self.state = 'cancel'

    def _create_stock_move(self, product, quantity, move_type, source_location, dest_location, partner=None):
        """
        Crea un movimiento de stock para consumo o producción.
        
        Args:
            product: product.product record
            quantity: Cantidad a mover
            move_type: 'out' (consumo) o 'in' (producción)
            source_location: stock.location record
            dest_location: stock.location record
            partner: res.partner record (opcional) - Contacto asociado
        """
        self.ensure_one()
        
        picking_type = self.env.ref('stock.picking_type_internal')
        
        # Crear el picking (traslado interno)
        picking_vals = {
            'origin': f'Producción {self.name}',
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'partner_id': partner.id if partner else False,  # Agregar contacto
            'move_ids': [(0, 0, {
                'name': f'Producción {self.name} - {product.name}',
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'partner_id': partner.id if partner else False,  # También en el move
            })],
        }
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Confirmar y asignar
        picking.action_confirm()
        picking.action_assign()
        
        # Establecer cantidades
        for move in picking.move_ids:
            # Asegurar que el partner también esté en los move_lines si es necesario
            if move.move_line_ids:
                for move_line in move.move_line_ids:
                    if move_line.quantity == 0:
                        move_line.quantity = move.product_uom_qty
            else:
                move_line_vals = {
                    'product_id': move.product_id.id,
                    'quantity': move.product_uom_qty,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                }
                if partner:
                    move_line_vals['partner_id'] = partner.id
                move.move_line_ids = [(0, 0, move_line_vals)]
        
        # Validar
        picking.button_validate()
        
        return picking