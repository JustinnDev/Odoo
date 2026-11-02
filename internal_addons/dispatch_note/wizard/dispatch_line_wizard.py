from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import clean_context


class DispatchLineWizard(models.TransientModel):
    _name = 'dispatch.line.wizard'
    _description = 'Wizard para agregar pesaje a nota de despacho'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    note_id = fields.Many2one(
        'dispatch.note',
        required=True,
        domain=[('state', '=', 'draft')],
    )
    product_id = fields.Many2one('product.product', required=True)
    type = fields.Char()
    gross_weight = fields.Float(digits='Product Unit of Measure')
    tare_weight = fields.Float(digits='Product Unit of Measure')
    net_weight = fields.Float(
        compute='_compute_net_weight',
        store=False,
        digits='Product Unit of Measure',
    )

    @api.depends('gross_weight', 'tare_weight')
    def _compute_net_weight(self):
        for wizard in self:
            wizard.net_weight = (wizard.gross_weight or 0.0) - (wizard.tare_weight or 0.0)

    @api.model
    def _get_source(self, model, res_id):
        if model not in self.env:
            raise UserError(_('El modelo %s no existe.') % model)
        source = self.env[model].browse(res_id)
        if not source.exists():
            raise UserError(_('El registro no existe.'))
        if not hasattr(source, '_prepare_dispatch_line_vals'):
            raise UserError(_('El modelo %s no soporta despacho.') % model)
        return source

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res_model = res.get('res_model')
        res_id = res.get('res_id')
        if res_model and res_id:
            source = self._get_source(res_model, res_id)
            vals = source._prepare_dispatch_line_vals() or {}
            for key in ('product_id', 'gross_weight', 'tare_weight', 'type'):
                if key in fields_list and key in vals:
                    res[key] = vals[key]
        return res

    def action_confirm(self):
        self.ensure_one()
        source = self._get_source(self.res_model, self.res_id)
        source._check_dispatch_line_allowed()
        if self.note_id.state != 'draft':
            raise UserError(_('La nota de despacho debe estar en estado En Proceso.'))
        if (self.net_weight or 0.0) <= 0:
            raise UserError(_('El peso neto debe ser mayor a cero.'))
        line = self.env['dispatch.note.line'].with_context(
            clean_context(self.env.context)
        ).create({
            'note_id': self.note_id.id,
            'product_id': self.product_id.id,
            'type': self.type or False,
            'gross_weight': self.gross_weight,
            'tare_weight': self.tare_weight,
        })
        self.note_id.message_post(
            body=Markup('Pesaje agregado desde <b>%s</b>: %s')
            % (source._description, source.display_name)
        )
        source._after_dispatch_line_created(line)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Pesaje agregado'),
                'message': self.note_id.display_name,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }