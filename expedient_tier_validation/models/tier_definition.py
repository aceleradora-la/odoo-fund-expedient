# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class TierDefinition(models.Model):
    _inherit = "tier.definition"

    @api.model
    def _get_tier_validation_model_names(self):
        """Incluir fund.expedient en los modelos disponibles para definiciones de nivel."""
        result = super()._get_tier_validation_model_names()
        if "fund.expedient" not in result:
            result.append("fund.expedient")
        return result
