from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DispatchNote(models.Model):
    _name = 'dispatch.note'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Nota de Entrega'
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
        string='Cliente',
        required=True
    )

    customer_ref = fields.Char(
        string='Referencia del cliente',
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
        ('processed', 'Procesado'),
        ('sale_created', 'Confirmado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True,
        copy=False
    )

    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Movimiento de Inventario',
        readonly=True,
        copy=False
    )

    note = fields.Text(string='Notas internas')

    line_ids = fields.One2many(
        'dispatch.note.line',
        'note_id',
        string='Líneas de Pesaje'
    )

    summary_ids = fields.One2many(
        'dispatch.note.summary',
        'note_id',
        string='Resumen por Material'
    )

    subtotal_kg = fields.Float(
        string='SubTotal kg',
        compute='_compute_totals',
        store=True
    )

    total_kg = fields.Float(
        string='Total Kg',
        compute='_compute_totals',
        store=True
    )

    total_amount = fields.Float(
        string='Total a Cobrar',
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

    vehicle_model = fields.Char(
        string='Modelo',
        readonly=False
    )

    vehicle_plate = fields.Char(
        string='Placa',
        readonly=False
    )

    trailer_plate = fields.Char(
        string='Placa del Remolque',
        readonly=False,
        help='Dejar vacío si es la misma que el vehículo'
    )

    driver_name = fields.Char(
        string='Nombre y Apellido',
        readonly=False
    )

    driver_id_number = fields.Char(
        string='C.I',
        readonly=False
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('dispatch.note') or _('Nuevo')
        return super().create(vals)

    @api.depends('summary_ids.total_kg', 'summary_ids.amount', 'summary_ids.subtotal_kg')
    def _compute_totals(self):
        for note in self:
            note.total_kg = sum(line.total_kg for line in note.summary_ids)
            note.total_amount = sum(line.amount for line in note.summary_ids)
            note.subtotal_kg = sum(line.subtotal_kg for line in note.summary_ids)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for note in self:
            note.line_count = len(note.line_ids)

    def action_compute_summary(self):
        """Agrupa las líneas de pesaje por producto Y tipo y genera las líneas de resumen."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas de pesaje para agrupar.'))

        # Guardar los precios y descuentos existentes por producto + tipo antes de eliminar
        existing_prices = {}
        existing_discounts = {}
        for summary in self.summary_ids:
            if summary.product_id:
                key = (summary.product_id.id, summary.type or '')
                existing_prices[key] = summary.price_unit
                existing_discounts[key] = summary.discount_percent

        # Eliminar resúmenes existentes (sin registrar en el chatter)
        self.summary_ids.with_context(dispatch_no_log=True).unlink()

        # Diccionario para acumular subtotales por producto + tipo
        group_data = {}

        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_('Todas las líneas de pesaje deben tener un producto asignado.'))

            key = (line.product_id.id, line.type or '')

            if key in group_data:
                group_data[key]['subtotal_kg'] += line.net_weight
                group_data[key]['line_count'] += 1
            else:
                # Usar precio y descuento existentes si están disponibles
                price = existing_prices.get(key, line.product_id.list_price or 0.0)
                discount = existing_discounts.get(key, 0.0)

                group_data[key] = {
                    'product_id': line.product_id.id,
                    'line_count': 1,
                    'type': line.type or '',
                    'subtotal_kg': line.net_weight,
                    'discount_percent': discount,
                    'price_unit': price,
                }

        # Crear líneas de resumen
        summary_lines = []
        for data in group_data.values():
            summary_lines.append((0, 0, data))
        self.with_context(dispatch_no_log=True).write({'summary_ids': summary_lines})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dispatch.note',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_generate_sale_order(self):
        """Genera la orden de venta desde el resumen, la confirma y valida la entrega.

        Todas las fechas (orden de venta, entrega y movimientos) quedan
        igualadas a la hora de salida (exit_time) de la nota.
        """
        self.ensure_one()

        # Verificar si ya existe una orden de venta
        if self.sale_order_id:
            raise UserError(_('Ya se ha generado una orden de venta para esta nota de despacho.'))

        if self.state not in ['draft', 'processed']:
            raise UserError(_('Solo se puede generar la orden de venta en estado En Proceso o Procesado.'))
        if not self.summary_ids:
            raise UserError(_('Debe generar primero el resumen por material.'))

        # Fecha única para todo el proceso
        exit_time = self.exit_time or fields.Datetime.now()

        # Crear la orden de venta
        so_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'client_order_ref': self.customer_ref,
            'date_order': exit_time,
        }
        sale_order = self.env['sale.order'].create(so_vals)

        # Agrupar por producto (sumando todos los tipos)
        product_totals = {}
        for summary in self.summary_ids:
            if summary.total_kg > 0:
                product_id = summary.product_id.id
                if product_id in product_totals:
                    product_totals[product_id]['product_uom_qty'] += summary.total_kg
                else:
                    product_totals[product_id] = {
                        'product_id': summary.product_id.id,
                        'product_uom_qty': summary.total_kg,
                        'price_unit': summary.price_unit,
                        'name': summary.product_id.display_name,
                    }

        # Crear líneas de la orden de venta
        so_lines = []
        for data in product_totals.values():
            so_lines.append((0, 0, data))

        if not so_lines:
            sale_order.unlink()
            raise UserError(_('No hay líneas con cantidad positiva para generar la orden de venta.'))

        sale_order.write({'order_line': so_lines})

        # Confirmar la cotización (action_confirm)
        sale_order.action_confirm()

        # action_confirm reescribe date_order con la fecha actual: forzarla de nuevo
        sale_order.write({'date_order': exit_time})

        # Entregas generadas por la orden de venta (equivale a action_view_delivery)
        pickings = sale_order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        ).sorted('id')

        last_picking = self.env['stock.picking']
        for picking in pickings:
            picking.scheduled_date = exit_time

            # Cantidad hecha = cantidad demandada
            for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                move.quantity = move.product_uom_qty
                if 'picked' in move._fields:
                    move.picked = True

            # Validar la entrega (button_validate)
            picking.button_validate()
            if picking.state != 'done':
                raise UserError(_(
                    'No se pudo validar automáticamente la entrega %s. '
                    'Revise el stock disponible o los datos del movimiento.'
                ) % picking.name)

            # Forzar fechas después de validar
            picking.write({'date_done': exit_time})
            picking.move_ids.write({'date': exit_time})
            picking.move_ids.move_line_ids.write({'date': exit_time})
            last_picking = picking

        # Actualizar la nota de despacho
        vals = {
            'sale_order_id': sale_order.id,
            'state': 'sale_created',
            'exit_time': exit_time,
        }
        if last_picking:
            vals['stock_picking_id'] = last_picking.id
        self.write(vals)

        # Recargar la nota de despacho
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dispatch.note',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_set_processed(self):
        """Marca la nota como procesada y registra la hora de salida."""
        self.ensure_one()
        if not self.summary_ids:
            raise UserError(_('Debe generar el resumen antes de marcar como procesado.'))
        self.write({
            'state': 'processed',
            'exit_time': fields.Datetime.now(),
        })

    def action_set_draft(self):
        """Vuelve a poner la nota en estado En Proceso."""
        self.ensure_one()
        if self.state not in ['processed', 'cancel']:
            raise UserError(_('Solo se puede volver a En Proceso desde Procesado o Cancelado.'))
        self.write({
            'state': 'draft',
            'exit_time': False,
        })

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancel'})