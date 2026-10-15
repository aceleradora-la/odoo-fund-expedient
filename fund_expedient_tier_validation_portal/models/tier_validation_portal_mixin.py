# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import AccessError, UserError


class TierValidationPortalMixin(models.AbstractModel):
    """Acciones tier reutilizables desde rutas HTTP del portal.

    Las acciones corren con `sudo()` porque un usuario de portal no tiene
    permiso de escritura sobre estos modelos. `sudo()` no cambia el usuario:
    los campos por usuario (`can_review`, `can_edit_in_stage`,
    `expedient_stage_editable`) siguen evaluándose para quien hizo la
    petición, y por eso los permisos funcionales se verifican acá ANTES de
    escalar. El backend salta su propia comprobación de etapa bajo sudo
    (`_check_stage_user_for_tier_action`) confiando en que el portal ya la
    hizo: esa confianza se cumple en `_portal_tier_ensure_flow_driver`.
    """

    _name = "tier.validation.portal.mixin"
    _description = "Tier validation — helpers portal"

    def _portal_tier_ensure_reviewer(self):
        self.ensure_one()
        if not getattr(self, "can_review", False):
            raise AccessError(_("No tiene una aprobación pendiente en este registro."))

    def _portal_tier_can_drive_flow(self):
        """True si el usuario actual opera la etapa del expediente del registro.

        Solicitar y reiniciar la validación empujan (o dan de baja) el circuito,
        que pertenece a la etapa: la misma regla que el backend. Las
        Solicitudes, Disposiciones y Resoluciones lo exponen como
        `expedient_stage_editable`; el expediente redefine este método.
        """
        self.ensure_one()
        return bool(getattr(self, "expedient_stage_editable", False))

    def _portal_tier_ensure_flow_driver(self, action):
        if not self._portal_tier_can_drive_flow():
            raise AccessError(
                _("Solo los usuarios asignados a la etapa actual del expediente pueden %s.")
                % action
            )

    def _portal_tier_current_reviews(self):
        self.ensure_one()
        if hasattr(self, "_current_context_reviews"):
            return self._current_context_reviews()
        if hasattr(self, "_current_stage_reviews"):
            return self._current_stage_reviews()
        return self.review_ids

    def _portal_tier_current_reviews_for_user(self):
        self.ensure_one()
        reviews = self._portal_tier_current_reviews()
        sequences = self._get_sequences_to_approve(self.env.user)
        return reviews.filtered(
            lambda r: r.status == "pending"
            and (r.approve_sequence_bypass or r.sequence in sequences)
        )

    def _portal_tier_write_comment(self, reviews, comment):
        comment = (comment or "").strip()
        if self.has_comment and not comment:
            raise UserError(_("Debe ingresar un comentario."))
        user_reviews = reviews.filtered(lambda r: self.env.user in r.reviewer_ids)
        if comment and user_reviews:
            user_reviews.sudo().write({"comment": comment})

    def portal_action_request_validation(self):
        self.ensure_one()
        self._portal_tier_ensure_flow_driver(_("solicitar la aprobación"))
        return self.sudo().request_validation()

    def portal_action_validate_tier(self, comment):
        self.ensure_one()
        self._portal_tier_ensure_reviewer()
        reviews = self._portal_tier_current_reviews_for_user()
        if not reviews:
            raise UserError(_("No hay una revisión pendiente que le corresponda aprobar."))
        self._portal_tier_write_comment(reviews, comment)
        record = self.sudo()
        record._validate_tier(reviews)
        record._update_counter({"review_deleted": True})
        if hasattr(record, "_on_context_tier_validated"):
            record._on_context_tier_validated()
        return True

    def portal_action_reject_tier(self, comment):
        self.ensure_one()
        self._portal_tier_ensure_reviewer()
        reviews = self._portal_tier_current_reviews_for_user()
        if not reviews:
            raise UserError(_("No hay una revisión pendiente que le corresponda rechazar."))
        self._portal_tier_write_comment(reviews, comment)
        record = self.sudo()
        record._rejected_tier(reviews)
        record._update_counter({"review_deleted": True})
        return True

    def portal_action_restart_validation(self):
        self.ensure_one()
        self._portal_tier_ensure_flow_driver(_("reiniciar la validación"))
        if not getattr(self, "can_restart_validation_stage", False):
            raise UserError(_("No hay una validación que reiniciar."))
        return self.sudo().restart_validation()
