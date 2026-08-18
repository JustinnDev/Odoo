from odoo import models, fields, api

class ReceptionNoteLine(models.Model):
    _name = 'reception.note.line'
    _description = 'Línea de Pesaje'
    _order = 'id'

    note_id = fields.Many2one(
        'reception.note',
        string='Nota de Recepción',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Material',
        required=True,
    )

    gross_weight = fields.Float(
        string='Peso Bruto',
        required=True,
        digits='Product Unit of Measure'
    )

    tare_weight = fields.Float(
        string='Peso Tara',
        required=True,
        digits='Product Unit of Measure'
    )

    net_weight = fields.Float(
        string='Peso Neto',
        compute='_compute_net_weight',
        store=True,
        digits='Product Unit of Measure'
    )

    @api.depends('gross_weight', 'tare_weight')
    def _compute_net_weight(self):
        for line in self:
            line.net_weight = line.gross_weight - line.tare_weight