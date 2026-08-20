from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ReceptionNote(models.Model):
    _name = 'reception.note'
    _description = 'Nota de Recepción'
    _order = 'entry_time desc, id desc'

    name = fields.Char(
        string='Número',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo')
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True
    )

    supplier_ref = fields.Char(
        string='Referencia del proveedor',
        help='Placa del vehículo, número de guía, etc.'
    )

    entry_time = fields.Datetime(
        string='Fecha y hora de entrada',
        required=True,
        default=fields.Datetime.now,
        readonly=False
    )

    exit_time = fields.Datetime(
        string='Fecha y hora de salida',
        readonly=False
    )

    state = fields.Selection([
        ('draft', 'En Proceso'),
        ('received', 'Procesado'),
        ('purchase_created', 'Confirmado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra',
        readonly=True,
        copy=False
    )

    note = fields.Text(string='Notas internas')

    line_ids = fields.One2many(
        'reception.note.line',
        'note_id',
        string='Líneas de Pesaje'
    )

    summary_ids = fields.One2many(
        'reception.note.summary',
        'note_id',
        string='Resumen por Material'
    )

    total_kg = fields.Float(
        string='Total Kg',
        compute='_compute_totals',
        store=True
    )

    total_amount = fields.Float(
        string='Total a Pagar',
        compute='_compute_totals',
        store=True,
        digits='Product Price' 
    )

    currency_id = fields.Many2one(
    'res.currency',
    string='Moneda',
    default=lambda self: self.env.company.currency_id.id,
    readonly=True
    )

    line_count = fields.Integer(
    string='Total Pesadas',
    compute='_compute_line_count',
    store=True
    )

    stock_picking_id = fields.Many2one(
    'stock.picking',
    string='Movimiento de Inventario',
    readonly=True,
    copy=False
)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('reception.note') or _('Nuevo')
        return super().create(vals)

    @api.depends('summary_ids.total_kg', 'summary_ids.amount')
    def _compute_totals(self):
        for note in self:
            note.total_kg = sum(line.total_kg for line in note.summary_ids)
            note.total_amount = sum(line.amount for line in note.summary_ids)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for note in self:
            note.line_count = len(note.line_ids)

    def action_compute_summary(self):
        """Agrupa las líneas de pesaje por producto y genera las líneas de resumen."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas de pesaje para agrupar.'))

        # Guardar los precios y descuentos existentes por producto antes de eliminar
        existing_prices = {}
        existing_discounts = {}
        for summary in self.summary_ids:
            if summary.product_id:
                existing_prices[summary.product_id.id] = summary.price_unit
                existing_discounts[summary.product_id.id] = summary.discount_percent

        # Eliminar resúmenes existentes
        self.summary_ids.unlink()

        # Diccionario para acumular subtotales por producto
        group_data = {}
        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_('Todas las líneas de pesaje deben tener un producto asignado.'))
            
            if line.product_id.id in group_data:
                group_data[line.product_id.id]['subtotal_kg'] += line.net_weight
            else:
                # Usar precio y descuento existentes si están disponibles, sino usar valores por defecto
                price = existing_prices.get(line.product_id.id, line.product_id.standard_price or 0.0)
                discount = existing_discounts.get(line.product_id.id, 0.0)
                
                group_data[line.product_id.id] = {
                    'product_id': line.product_id.id,
                    'subtotal_kg': line.net_weight,
                    'discount_percent': discount,
                    'price_unit': price,
                }

        # Crear líneas de resumen
        summary_lines = []
        for data in group_data.values():
            summary_lines.append((0, 0, data))
        self.write({'summary_ids': summary_lines})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reception.note',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_generate_purchase_order(self):
        """Genera una orden de compra (RFQ) a partir del resumen. Y tambien validacion de movimiento en el inventario"""
        self.ensure_one()

        # Verificar si ya existe una orden de compra
        if self.purchase_order_id:
            raise UserError(_('Ya se ha generado una orden de compra para esta nota de recepción.'))

        # Verificar si el usuario tiene permisos para generar órdenes de compra
        if not self.env.user.has_group('reception_note.group_generate_purchase_order'):
            raise UserError(_('No tiene permisos para generar órdenes de compra.'))

        if self.state not in ['draft', 'received','facturado']:
            raise UserError(_('Solo se puede generar la orden de compra en estado En Proceso o Recibido.'))
        if not self.summary_ids:
            raise UserError(_('Debe generar primero el resumen por material.'))

        # Crear la orden de compra con la referencia del proveedor
        po_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'partner_ref': self.supplier_ref,
            'date_order': fields.Datetime.now(),
        }
        purchase_order = self.env['purchase.order'].create(po_vals)

        # Crear líneas de la orden de compra (solo cantidades positivas)
        po_lines = []
        for summary in self.summary_ids:
            # Solo incluir líneas con cantidad positiva
            if summary.total_kg > 0:
                po_lines.append((0, 0, {
                    'product_id': summary.product_id.id,
                    'product_qty': summary.total_kg,
                    'price_unit': summary.price_unit,
                    'name': summary.product_id.display_name,
                }))
            elif summary.total_kg < 0:
                # Opcional: mostrar una advertencia sobre líneas negativas
                print(f"Advertencia: {summary.product_id.display_name} tiene cantidad negativa ({summary.total_kg} kg) y no se incluirá en la orden de compra.")
        
        if not po_lines:
            raise UserError(_('No hay líneas con cantidad positiva para generar la orden de compra.'))
        
        purchase_order.write({'order_line': po_lines})

         # Confirmar automáticamente la orden de compra
        purchase_order.button_confirm()
        
        # Buscar el picking (recepción) generado por la orden de compra
        picking = self.env['stock.picking'].search([
            ('purchase_id', '=', purchase_order.id),
            ('state', 'not in', ['done', 'cancel'])
        ], limit=1)
        
        if picking:
            # Validar la recepción de inventario
            for move in picking.move_ids:
                if move.state != 'done':
                    if move.move_line_ids:
                        # Actualizar líneas existentes
                        for move_line in move.move_line_ids:
                            # En Odoo 18, se usa 'quantity' para la cantidad recibida
                            move_line.quantity = move.product_uom_qty
                    else:
                        # Crear línea si no existe
                        move.move_line_ids = [(0, 0, {
                            'product_id': move.product_id.id,
                            'quantity': move.product_uom_qty,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                        })]
            
            picking.button_validate()
            
            self.write({
                'purchase_order_id': purchase_order.id,
                'stock_picking_id': picking.id,
                'state': 'purchase_created',
                'exit_time': fields.Datetime.now(),
            })

        # Abrir la orden de compra creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_set_received(self):
        """Marca la nota como recibida y registra la hora de salida."""
        self.ensure_one()
        if not self.summary_ids:
            raise UserError(_('Debe generar el resumen antes de marcar como recibido.'))
        self.write({
            'state': 'received',
            'exit_time': fields.Datetime.now(),
        })

    def action_set_draft(self):
        """Vuelve a poner la nota en estado En Proceso."""
        self.ensure_one()
        if self.state not in ['received', 'cancel']:
            raise UserError(_('Solo se puede volver a En Proceso desde Recibido o Cancelado.'))
        self.write({
            'state': 'draft',
            'exit_time': False,
        })

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancel'})