# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import AccessError


class FundExpedientResolution(models.Model):
    _name = "fund.expedient.resolution"
    _inherit = ["fund.expedient.resolution", "tier.validation.portal.mixin"]

    def _portal_tier_check_access(self):
        self.ensure_one()
        if not self.expedient_id._portal_user_can_access():
            raise AccessError(_("No tiene acceso a este expediente."))
