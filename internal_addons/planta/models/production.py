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


    @api.model
    def _get_production_location(self):
        """Obtiene o crea la ubicación virtual de producción"""
        location = self.env['stock.location'].search([
            ('name', '=', 'PLANTA/Produccion'),
            ('usage', '=', 'production')
        ], limit=1)
        
        if not location:
            # Crear ubicación virtual de producción
            location = self.env['stock.location'].create({
                'name': 'PLANTA/Produccion',
                'usage': 'production',  # Importante: 'production' para que sea virtual
                'company_id': self.env.company.id,
            })
        return location
    
    def action_process(self):
        """Procesa la producción con movimientos visualmente correctos"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede procesar una producción en borrador.'))
        
        if not self.creator_ids:
            raise UserError(_('Debe añadir al menos un creador.'))
        
        # Verificar stock disponible
        real_qty = self.env['stock.quant']._get_available_quantity(
            self.product_from_id,
            self.source_location_id,
            allow_negative=True  # Permitir stock negativo
        )

        if real_qty < self.quantity:
            raise UserError(_(
                'Stock insuficiente de %s. Disponible: %s, Requerido: %s',
                self.product_from_id.name,
                real_qty,
                self.quantity
            ))

        print("...................................................")
        print(real_qty)
        
        # Obtener ubicación virtual de producción
        production_loc = self._get_production_location()
        
        # === MOVIMIENTO 1: Consumo (WH/Existencias -> WH/PLANTA/PRODUCCION) ===
        # Este aparecerá en ROJO (salida)
        self._create_production_move(
            product=self.product_from_id,
            quantity=self.quantity,
            source_location=self.source_location_id,
            dest_location=production_loc,  # Ubicación virtual
            move_type='out'
        )
        
        # === MOVIMIENTO 2: Producción (WH/PLANTA/PRODUCCION -> WH/Existencias) ===
        # Este aparecerá en VERDE (entrada)
        self._create_production_move(
            product=self.product_to_id,
            quantity=self.quantity,
            source_location=production_loc,  # Ubicación virtual
            dest_location=self.dest_location_id,
            move_type='in'
        )
        
        self.write({
            'state': 'done',
            'date': fields.Datetime.now()
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


    def _create_production_move(self, product, quantity, source_location, dest_location, move_type):
        """
        Crea un movimiento de stock para producción con colores correctos
        
        Args:
            move_type: 'out' (consumo - rojo) o 'in' (producción - verde)
        """
        self.ensure_one()
        
        # Determinar el tipo de picking según sea salida o entrada
        if move_type == 'out':
            picking_type = self.env.ref('stock.picking_type_out')  # Salida (rojo)
            operation_name = 'Consumo'
        else:
            picking_type = self.env.ref('stock.picking_type_in')   # Entrada (verde)
            operation_name = 'Producción'
        
        # Crear el picking
        picking_vals = {
            'origin': f'Producción {self.name}',
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'move_ids': [(0, 0, {
                'name': f'{operation_name}: {product.name}',
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'partner_id': self.partner_id.id if self.partner_id else False,
            })],
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        picking.action_confirm()
        picking.action_assign()
        
        # Configurar cantidades
        for move in picking.move_ids:
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
                move.move_line_ids = [(0, 0, move_line_vals)]
        
        # Validar el picking
        picking.button_validate()
        
        return picking