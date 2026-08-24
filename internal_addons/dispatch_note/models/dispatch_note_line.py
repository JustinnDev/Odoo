from odoo import models, fields, api

class DispatchNoteLine(models.Model):
    _name = 'dispatch.note.line'
    _description = 'Línea de Pesaje'
    _order = 'id'

    note_id = fields.Many2one(
        'dispatch.note',
        string='Nota de Despacho',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Material',
        required=True,
    )

    gross_weight = fields.Float(
        string='Bruto',
        required=True,
        digits='Product Unit of Measure'
    )

    tare_weight = fields.Float(
        string='Tara',
        required=True,
        digits='Product Unit of Measure'
    )

    net_weight = fields.Float(
        string='Neto',
        compute='_compute_net_weight',
        store=True,
        digits='Product Unit of Measure'
    )

    type = fields.Char(
    string='Tipo',
    required=False,
    help='Especificar el tipo de material (Paca, Máquina, Motor, etc.)'
    )

    @api.depends('gross_weight', 'tare_weight')
    def _compute_net_weight(self):
        for line in self:
            line.net_weight = line.gross_weight - line.tare_weight


    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Forzar guardado del padre después de crear líneas
        for line in lines:
            if line.note_id:
                line.note_id.write({})
                # Recalcular Resumen
                if line.note_id.state == 'draft':
                    line.note_id.action_compute_summary()
        return lines

    def write(self, vals):
        result = super().write(vals)
        # Forzar guardado del padre después de modificar líneas
        for line in self:
            if line.note_id:
                line.note_id.write({})
                # Recalcular Resumen
                if line.note_id.state == 'draft':
                    line.note_id.action_compute_summary()
        return result