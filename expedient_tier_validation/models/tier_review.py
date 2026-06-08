# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

_FUND_EXPEDIENT_MODELS = (
    "fund.expedient",
    "fund.expedient.spend.request",
    "fund.expedient.disposition",
    "fund.expedient.resolution",
)


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

    def _fill_fund_context_vals(self, vals, review=None):
        """Completar etapa/fase en reviews creadas fuera de request_validation (p. ej. forward)."""
        model = vals.get("model") or (review.model if review else False)
        res_id = vals.get("res_id") or (review.res_id if review else False)
        if not model or not res_id:
            return
        stage_id = vals.get("stage_id") or (review.stage_id.id if review and review.stage_id else False)
        spend_phase = vals.get("spend_phase") or (review.spend_phase if review else False)
        if model == "fund.expedient" and not stage_id:
            expedient = self.env["fund.expedient"].browse(res_id).exists()
            if expedient.stage_id:
                vals["stage_id"] = expedient.stage_id.id
        elif model == "fund.expedient.spend.request" and not spend_phase:
            spend_request = self.env["fund.expedient.spend.request"].browse(res_id).exists()
            if spend_request:
                vals["spend_phase"] = spend_request._get_active_spend_phase()
        elif model in ("fund.expedient.disposition", "fund.expedient.resolution") and not stage_id:
            record = self.env[model].browse(res_id).exists()
            if record.stage_id:
                vals["stage_id"] = record.stage_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("model") in _FUND_EXPEDIENT_MODELS:
                self._fill_fund_context_vals(vals)
        records = super().create(vals_list)
        records._backfill_missing_context()
        return records

    def _backfill_missing_context(self):
        """Corregir reviews ya creadas sin etapa/fase (p. ej. forward antes del fix)."""
        for review in self.filtered(lambda r: r.model in _FUND_EXPEDIENT_MODELS):
            patch = {}
            review._fill_fund_context_vals(patch, review=review)
            if patch:
                super(TierReview, review).write(patch)

    def write(self, vals):
        res = super().write(vals)
        self._backfill_missing_context()
        return res

    def _pending_reviews_same_context(self, resource):
        """Reviews pendientes del mismo contexto (etapa/fase), tolerando filas sin contexto."""
        self.ensure_one()
        if self.model == "fund.expedient.spend.request":
            phase = resource._get_active_spend_phase()
            return resource.review_ids.filtered(
                lambda r: r.status == "pending"
                and (r.spend_phase == phase or not r.spend_phase)
            )
        if self.model in ("fund.expedient.disposition", "fund.expedient.resolution"):
            return resource.review_ids.filtered(
                lambda r: r.status == "pending"
                and (r.stage_id == resource.stage_id or not r.stage_id)
            )
        return resource.review_ids.filtered(
            lambda r: r.status == "pending"
            and (r.stage_id == resource.stage_id or not r.stage_id)
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
        resource = self.env[self.model].browse(self.res_id)
        reviews = self._pending_reviews_same_context(resource)
        if not reviews:
            return True
        sequence = min(reviews.mapped("sequence"))
        return self.sequence == sequence

