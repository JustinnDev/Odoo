from odoo import models, fields, api
import math

class ReceptionNoteSummary(models.Model):
    _name = 'reception.note.summary'
    _description = 'Resumen por Material'
    _order = 'product_id'

    note_id = fields.Many2one(
        'reception.note',
        string='Nota de Recepción',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Material',
        required=True
    )

    subtotal_kg = fields.Float(
        string='Subtotal',
        required=True,
        digits='Product Unit of Measure'
    )

    discount_percent = fields.Float(
        string='Desc. %',
        default=0.0,
        digits='Discount'
    )

    discount_kg = fields.Float(
        string='Desc. ',
        compute='_compute_discount_kg',
        store=True,
        digits='Product Unit of Measure'
    )

    total_kg = fields.Float(
        string='Total',
        compute='_compute_total_kg',
        store=True,
        digits='Product Unit of Measure'
    )

    price_unit = fields.Float(
        string='Precio Unitario',
        required=True,
        digits='Product Price'
    )

    amount = fields.Float(
        string='Importe',
        compute='_compute_amount',
        store=True,
        digits='Product Price'
    )

    type = fields.Char(
    string='Tipo',
    required=False
)

    @api.depends('subtotal_kg', 'discount_percent')
    def _compute_discount_kg(self):
        for line in self:
            result = line.subtotal_kg * (line.discount_percent / 100.0)
            line.discount_kg = math.ceil(result)
            print("reception_note_summary_compute_discount_kg")

    @api.depends('subtotal_kg', 'discount_kg')
    def _compute_total_kg(self):
        for line in self:
            line.total_kg = line.subtotal_kg - line.discount_kg

    @api.depends('total_kg', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.amount = line.total_kg * line.price_unit