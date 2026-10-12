from markupsafe import Markup
from odoo import models, fields, api, _

TRACKED_FIELDS = {
    'product_id': 'Material',
    'type': 'Tipo',
    'gross_weight': 'Peso Bruto',
    'tare_weight': 'Tara',
}

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


    def _post_line_message(self, lines, title):
        """Publica en el chatter de la nota el detalle de las pesadas afectadas."""
        for line in lines:
            note = line.note_id
            if not note:
                continue
            body = Markup('<b>%s</b> - Material: %s - Bruto: %s - Tara: %s - Neto: %s') % (
                Markup(title),
                line.product_id.display_name or _('(sin material)'),
                line.gross_weight,
                line.tare_weight,
                line.net_weight,
            )
            note.message_post(body=body)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('reception_no_log'):
            self._post_line_message(lines, _('Pesaje agregado'))
        # Forzar guardado del padre y recalcular resumen
        for line in lines:
            if line.note_id:
                line.note_id.write({})
                # Recalcular resumen automáticamente
                if line.note_id.state == 'draft':
                    line.note_id.with_context(reception_no_log=True).action_compute_summary()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('reception_no_log'):
            self._post_line_message(self, _('Pesaje modificado'))
        # Forzar guardado del padre y recalcular resumen
        for line in self:
            if line.note_id:
                line.note_id.write({})
                # Recalcular resumen automáticamente
                if line.note_id.state == 'draft':
                    line.note_id.with_context(reception_no_log=True).action_compute_summary()
        return result

    def unlink(self):
        if not self.env.context.get('reception_no_log'):
            self._post_line_message(self, _('Pesaje eliminado'))
        return super().unlink()