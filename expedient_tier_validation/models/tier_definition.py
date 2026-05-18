# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class TierDefinition(models.Model):
    _inherit = "tier.definition"

    @api.model
    def _get_tier_validation_model_names(self):
        """Modelos fundación disponibles para definiciones de nivel."""
        result = super()._get_tier_validation_model_names()
        for model_name in (
            "fund.expedient",
            "fund.expedient.spend.request",
            "fund.expedient.disposition",
            "fund.expedient.resolution",
        ):
            if model_name not in result:
                result.append(model_name)
        return result
