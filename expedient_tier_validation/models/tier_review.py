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

    def _can_review_value(self):
        """Agrupar secuencia de aprobación solo entre reviews de la misma etapa del expediente."""
        self.ensure_one()
        if self.model != "fund.expedient":
            return super()._can_review_value()
        if self.status not in ("pending", "waiting"):
            return False
        if not self.approve_sequence:
            return True
        resource = self.env["fund.expedient"].browse(self.res_id)
        reviews = resource.review_ids.filtered(
            lambda r: r.status == "pending" and r.stage_id == resource.stage_id
        )
        if not reviews:
            return True
        sequence = min(reviews.mapped("sequence"))
        return self.sequence == sequence

