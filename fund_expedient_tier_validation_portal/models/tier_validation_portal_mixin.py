# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import AccessError, UserError


class TierValidationPortalMixin(models.AbstractModel):
    """Acciones tier reutilizables desde rutas HTTP del portal."""

    _name = "tier.validation.portal.mixin"
    _description = "Tier validation — helpers portal"

    def _portal_tier_ensure_reviewer(self):
        self.ensure_one()
        if not getattr(self, "can_review", False):
            raise AccessError(_("No tiene permisos para revisar este registro."))

    def _portal_tier_current_reviews_for_user(self):
        self.ensure_one()
        if hasattr(self, "_current_context_reviews"):
            reviews = self._current_context_reviews()
        else:
            reviews = self._current_stage_reviews()
        sequences = self._get_sequences_to_approve(self.env.user)
        return reviews.filtered(
            lambda r: r.status == "pending"
            and (r.approve_sequence_bypass or r.sequence in sequences)
        )

    def portal_action_request_validation(self):
        self.ensure_one()
        return self.request_validation()

    def portal_action_validate_tier(self, comment):
        self.ensure_one()
        self._portal_tier_ensure_reviewer()
        if self.has_comment and not (comment or "").strip():
            raise UserError(_("Debe ingresar un comentario para aprobar."))
        reviews = self._portal_tier_current_reviews_for_user()
        user_reviews = reviews.filtered(
            lambda r: self.env.user in r.reviewer_ids
        )
        if comment and user_reviews:
            user_reviews.write({"comment": comment})
        if reviews:
            self._validate_tier(reviews)
            self._update_counter({"review_deleted": True})
            if hasattr(self, "_on_context_tier_validated"):
                self._on_context_tier_validated()
        return True

    def portal_action_reject_tier(self, comment):
        self.ensure_one()
        self._portal_tier_ensure_reviewer()
        if self.has_comment and not (comment or "").strip():
            raise UserError(_("Debe ingresar un comentario para rechazar."))
        reviews = self._portal_tier_current_reviews_for_user()
        user_reviews = reviews.filtered(
            lambda r: self.env.user in r.reviewer_ids
        )
        if comment and user_reviews:
            user_reviews.write({"comment": comment})
        if reviews:
            self._rejected_tier(reviews)
            self._update_counter({"review_deleted": True})
        return True

    def portal_action_restart_validation(self):
        self.ensure_one()
        if not getattr(self, "can_restart_validation_stage", False):
            raise AccessError(_("No puede reiniciar la validación en este contexto."))
        return self.restart_validation()
