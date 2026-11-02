from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DispatchLineSourceMixin(models.AbstractModel):
    _name = 'dispatch.line.source.mixin'
    _description = 'Mixin para modelos que pueden generar líneas de dispatch'

    def _prepare_dispatch_line_vals(self):
        """Devuelve un dict con product_id (id), gross_weight, tare_weight, type.

        Cada modelo que herede este mixin debe sobrescribirlo.
        """
        raise NotImplementedError

    def _check_dispatch_line_allowed(self):
        """Hook opcional: lanza UserError si no se puede despachar."""
        return

    def _after_dispatch_line_created(self, line):
        """Hook opcional ejecutado tras crear la línea de dispatch."""
        return

    def action_open_dispatch_wizard(self):
        self.ensure_one()
        self._check_dispatch_line_allowed()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agregar a Nota de Despacho'),
            'res_model': 'dispatch.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }