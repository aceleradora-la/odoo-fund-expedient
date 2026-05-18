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
    spend_phase = fields.Selection(
        selection=[
            ("preventiva", "Preventiva"),
            ("definitiva", "Definitiva"),
        ],
        string="Fase SG",
        index=True,
        help="Fase de la Solicitud de Gasto asociada a la revisión.",
    )

    def _can_review_value(self):
        """Agrupar secuencia de aprobación solo entre reviews de la misma etapa del expediente."""
        self.ensure_one()
        if self.model not in (
            "fund.expedient",
            "fund.expedient.spend.request",
            "fund.expedient.disposition",
            "fund.expedient.resolution",
        ):
            return super()._can_review_value()
        if self.status not in ("pending", "waiting"):
            return False
        if not self.approve_sequence:
            return True
        if self.model == "fund.expedient.spend.request":
            resource = self.env["fund.expedient.spend.request"].browse(self.res_id)
            phase = resource._get_active_spend_phase()
            reviews = resource.review_ids.filtered(
                lambda r: r.status == "pending" and r.spend_phase == phase
            )
        elif self.model in ("fund.expedient.disposition", "fund.expedient.resolution"):
            resource = self.env[self.model].browse(self.res_id)
            reviews = resource.review_ids.filtered(
                lambda r: r.status == "pending" and r.stage_id == resource.stage_id
            )
        else:
            resource = self.env["fund.expedient"].browse(self.res_id)
            reviews = resource.review_ids.filtered(
                lambda r: r.status == "pending" and r.stage_id == resource.stage_id
            )
        if not reviews:
            return True
        sequence = min(reviews.mapped("sequence"))
        return self.sequence == sequence

