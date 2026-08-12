# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
res.partner extension: pending approvals smart counter.

Surfaces "this partner has N approval requests in flight" on the partner
form. The number is computed (no storage, recomputed on form load) so a
new request appearing immediately reflects in the counter.

Why this lives here and not in res.partner core: each suite module
contributes its own smart-button counter for the metric it owns,
keeping coupling minimal. A buyer opening a vendor form sees:

  * Pending approvals  (from this module)
  * Active collections  (from eh_account_collections)
  * Open cheques  (from eh_account_pdc)
  * Overdue AR/AP  (from eh_account_credit_limit)
  * ...

Each card is one click into a filtered list of the underlying records.
"""

from odoo import api, fields, models
from odoo.addons.eh_account_base.tools.orm_compat import read_group_compat


class ResPartner(models.Model):
    _inherit = 'res.partner'

    eh_pending_approval_count = fields.Integer(
        compute='_compute_eh_pending_approval_count',
        help=(
            "Open approval requests on invoices/bills for this "
            "partner. Pending and in_review states count; approved, "
            "rejected, withdrawn and archived do not."
        ),
    )

    @api.depends_context('uid')
    def _compute_eh_pending_approval_count(self):
        Request = self.env['eh.approval.request'].sudo()

        for partner in self:
            count = Request.search_count([  # <-- IMPORTANTE: search_count, NO search.count
                ('move_id.partner_id', '=', partner.id),
                ('state', 'in', ('pending', 'in_review'))
            ])
            partner.eh_pending_approval_count = count

    def action_view_eh_pending_approvals(self):
        """Open the approval-request list filtered to this partner."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending approvals',
            'res_model': 'eh.approval.request',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [
                ('move_id.partner_id', '=', self.id),
                ('state', 'in', ('pending', 'in_review')),
            ],
            'context': {'default_move_id': False},
        }
