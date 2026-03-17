# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TierReview(models.Model):
    _inherit = "tier.review"

    stage_id = fields.Many2one(
        comodel_name="fund.expedient.stage",
        string="Etapa (Expediente)",
        index=True,
        help="Etapa del expediente al momento de solicitar/crear la revisión.",
    )

