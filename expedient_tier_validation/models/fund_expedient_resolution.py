# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FundExpedientResolution(models.Model):
    _name = "fund.expedient.resolution"
    _inherit = ["fund.expedient.resolution", "mail.thread", "tier.validation", "fund.tier.validation.mixin"]

    _tier_validation_manual_config = False
    _state_from = ["draft", "in_progress", "purchases", "to_approve", "approved"]
    _state_to = ["approved"]
    _cancel_state = "cancel"

    state = fields.Selection(related="expedient_id.state", store=True, readonly=True)

    def _tier_review_context_field(self):
        return "stage_id"

    def _tier_context_value(self):
        return self.stage_id

    def _get_company(self):
        self.ensure_one()
        return self.expedient_id.company_id or self.env.company
