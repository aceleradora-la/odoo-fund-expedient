# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "tier.validation"]
    _state_from = ["draft", "in_progress", "to_approve"]
    _state_to = ["approved"]
    _cancel_state = "cancel"
    _tier_validation_manual_config = False
    stage_validation_status = fields.Selection(
        selection=[
            ("no", "Without validation"),
            ("waiting", "Waiting"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("validated", "Validated"),
        ],
        compute="_compute_stage_validation",
        store=False,
    )
    has_stage_reviews = fields.Boolean(
        compute="_compute_stage_validation",
        store=False,
    )
    can_restart_validation_stage = fields.Boolean(
        string="Puede reiniciar validación (etapa)",
        compute="_compute_can_restart_validation_stage",
    )

    @api.depends("review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_can_restart_validation_stage(self):
        for rec in self:
            stage_reviews = rec.review_ids.filtered(lambda r: r.stage_id.id == rec.stage_id.id)
            rec.can_restart_validation_stage = bool(
                stage_reviews
                # Permitir reiniciar también si ya está aprobada (auditoría queda en reviews anteriores por etapa)
                and any(r.status in ("waiting", "pending", "rejected", "approved") for r in stage_reviews)
            )

    @api.depends("review_ids.status", "review_ids.stage_id", "stage_id")
    def _compute_stage_validation(self):
        for rec in self:
            stage_reviews = rec.review_ids.filtered(lambda r: r.stage_id.id == rec.stage_id.id)
            rec.has_stage_reviews = bool(stage_reviews)
            if not stage_reviews:
                rec.stage_validation_status = "no"
                continue
            statuses = set(stage_reviews.mapped("status"))
            if "rejected" in statuses:
                rec.stage_validation_status = "rejected"
            elif statuses == {"approved"}:
                rec.stage_validation_status = "validated"
            elif "pending" in statuses:
                rec.stage_validation_status = "pending"
            elif "waiting" in statuses:
                rec.stage_validation_status = "waiting"
            else:
                rec.stage_validation_status = "no"

    def _current_stage_reviews(self):
        """Reviews asociadas a la etapa actual (para validación por etapa)."""
        self.ensure_one()
        return self.review_ids.filtered(lambda r: r.stage_id.id == self.stage_id.id)

    def _is_current_stage_validated(self):
        """True si la etapa actual ya está aprobada (todas las reviews de la etapa en approved)."""
        self.ensure_one()
        stage_reviews = self._current_stage_reviews()
        return bool(stage_reviews) and all(r.status == "approved" for r in stage_reviews)

    def _prepare_tier_review_vals(self, definition, sequence):
        """Inyectar etapa actual en la review para auditoría por etapa."""
        vals = super()._prepare_tier_review_vals(definition, sequence)
        vals["stage_id"] = self.stage_id.id
        return vals

    def request_validation(self):
        """Solicitar validación y recargar la vista.

        En Odoo 18 el template QWeb de tier validation se inyecta en `get_view` y
        algunos cambios (botones/labels) no se reflejan hasta recargar.
        """
        super().request_validation()
        return {"type": "ir.actions.client", "tag": "reload"}

    def restart_validation(self):
        """Reiniciar solo la validación de la etapa actual (mantiene historial de otras etapas)."""
        for rec in self:
            rec._current_stage_reviews().sudo().unlink()
        # Recalcular status en el abstracto (counter / can_review)
        self.review_ids._compute_can_review()
        return True

    def action_next_stage(self):
        """No permitir pasar a la siguiente etapa hasta que la validación esté finalizada."""
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden pasar a la siguiente."
                    )
                )
            # Validación por etapa: si corresponde validación en esta etapa, no avanzar hasta aprobar.
            if rec.need_validation and not rec._is_current_stage_validated():
                stage_reviews = rec._current_stage_reviews()
                if not stage_reviews:
                    # Crea reviews para esta etapa (quedan etiquetadas con stage_id vía override)
                    rec.request_validation()
                raise UserError(
                    _(
                        "No puede pasar a la siguiente etapa hasta que la validación "
                        "esté finalizada. Solicite la validación y espere su aprobación."
                    )
                )
        # Hacer el cambio de etapa (el fund_expedient base con tier llama request_validation
        # y no avanza; aquí ya validamos, así que ejecutamos la transición de etapa).
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index == -1 or current_index + 1 >= len(stages):
                continue
            target = stages[current_index + 1]
            rec.with_context(skip_validation_check=True).write({"stage_id": target.id})
        return True

    def action_previous_stage(self):
        """Permitir volver de etapa usando skip_validation_check para no bloquear por tier validation."""
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden volver a la etapa anterior."
                    )
                )
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index <= 0:
                continue
            target = stages[current_index - 1]
            rec.with_context(skip_validation_check=True).write({"stage_id": target.id})
        return True
