from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DispatchNote(models.Model):
    _name = 'dispatch.note'
    _description = 'Nota de Despacho'
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
        """Agrupa las líneas de pesaje por producto Y tipo y genera las líneas de resumen."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No hay líneas de pesaje para agrupar.'))

        # Guardar los precios y descuentos existentes por producto antes de eliminar
        existing_prices = {}
        existing_discounts = {}
        for summary in self.summary_ids:
            if summary.product_id:
                # Usar producto + tipo como clave
                key = (summary.product_id.id, summary.type or '')
                existing_prices[key] = summary.price_unit
                existing_discounts[key] = summary.discount_percent

        # Eliminar resúmenes existentes
        self.summary_ids.unlink()

        # Diccionario para acumular subtotales por producto + tipo
        group_data = {}
        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_('Todas las líneas de pesaje deben tener un producto asignado.'))
            
            # Clave compuesta por producto + tipo
            key = (line.product_id.id, line.type or '')
            
            if key in group_data:
                group_data[key]['subtotal_kg'] += line.net_weight
            else:
                # Usar precio y descuento existentes si están disponibles
                price = existing_prices.get(key, line.product_id.list_price or 0.0)
                discount = existing_discounts.get(key, 0.0)
                
                group_data[key] = {
                    'product_id': line.product_id.id,
                    'type': line.type or '',
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
            'res_model': 'dispatch.note',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_generate_sale_order(self):
        """Genera una orden de venta a partir del resumen, agrupando por producto."""
        self.ensure_one()

        # Verificar si ya existe una orden de venta
        if self.sale_order_id:
            raise UserError(_('Ya se ha generado una orden de venta para esta nota de despacho.'))

        if self.state not in ['draft', 'processed']:
            raise UserError(_('Solo se puede generar la orden de venta en estado En Proceso o Procesado.'))
        if not self.summary_ids:
            raise UserError(_('Debe generar primero el resumen por material.'))

        # Crear la orden de venta
        so_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'client_order_ref': self.customer_ref,
            'date_order': fields.Datetime.now(),
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

        # Actualizar la nota de despacho
        self.write({
            'sale_order_id': sale_order.id,
            'state': 'sale_created',
            'exit_time': fields.Datetime.now(),
        })

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