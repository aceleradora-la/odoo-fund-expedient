# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FundExpedientDisposition(models.Model):
    _name = "fund.expedient.disposition"
    # Orden importa: mixin antes de tier.validation para que sus overrides ganen en MRO.
    _inherit = ["fund.expedient.disposition", "mail.thread", "fund.tier.validation.mixin", "tier.validation"]

    # Manual: el form de disposición se renderiza embebido en el expediente; no pasa por
    # el get_view de fund.expedient.disposition, por eso inyectamos los botones a mano.
    _tier_validation_manual_config = True
    _state_from = ["draft", "in_progress", "purchases", "to_approve", "approved"]
    _state_to = ["approved"]
    _cancel_state = "cancel"

    state = fields.Selection(related="expedient_id.state", store=True, readonly=True)

    def _tier_review_context_field(self):
        return "stage_id"

    def _tier_context_value(self):
        return self.stage_id

    def _get_company(self):
        if not self:
            return self.env.company
        return self[:1].expedient_id.company_id or self.env.company

    def _cancel_pending_approvals(self):
        """Al anular, quitar las validaciones abiertas (waiting/pending).

        Las ya aprobadas o rechazadas se conservan como historial de lo actuado.
        Sin esto, un registro anulado seguiría figurando en «Mis aprobaciones».
        """
        res = super()._cancel_pending_approvals()
        for rec in self:
            open_reviews = rec.review_ids.filtered(
                lambda r: r.status in ("waiting", "pending")
            )
            if open_reviews:
                open_reviews.sudo().unlink()
        return res
