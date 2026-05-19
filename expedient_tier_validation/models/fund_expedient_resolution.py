# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FundExpedientResolution(models.Model):
    _name = "fund.expedient.resolution"
    # Orden importa: mixin antes de tier.validation para que sus overrides ganen en MRO.
    _inherit = ["fund.expedient.resolution", "mail.thread", "fund.tier.validation.mixin", "tier.validation"]

    # Manual: idem disposición; el form de resolución vive embebido en el expediente.
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
