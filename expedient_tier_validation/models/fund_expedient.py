# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "tier.validation"]
    _state_from = ["draft", "in_progress", "to_approve"]
    _state_to = ["approved"]
    _cancel_state = "cancel"
    _tier_validation_manual_config = False
