# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

_TIER_DONE_STATUSES = ("approved", "forwarded")
_TIER_OPEN_STATUSES = ("pending", "waiting")


class FundTierApprovalSearchMixin(models.AbstractModel):
    """Campos de búsqueda para el menú Mis aprobaciones (pendientes, historial, vista admin)."""

    _name = "fund.tier.approval.search.mixin"
    _description = "Búsquedas Mis aprobaciones (tier)"

    tier_approval_pending_mine = fields.Boolean(search="_search_tier_approval_pending_mine")
    tier_approval_done_mine = fields.Boolean(search="_search_tier_approval_done_mine")
    tier_approval_pending_all = fields.Boolean(search="_search_tier_approval_pending_all")
    tier_approval_done_all = fields.Boolean(search="_search_tier_approval_done_all")

    def _approval_context_reviews(self):
        """Reviews del contexto activo (etapa o fase SG)."""
        self.ensure_one()
        if self._name == "fund.expedient":
            return self._current_stage_reviews()
        return self._current_context_reviews()

    @api.model
    def _res_ids_from_context_reviews(self, reviews):
        """res_id cuyas reviews pertenecen al contexto tier actual del registro."""
        if not reviews:
            return []
        res_ids = []
        for res_id in reviews.mapped("res_id"):
            record = self.browse(res_id).exists()
            if not record:
                continue
            ctx_ids = set(record._approval_context_reviews().ids)
            if any(r.id in ctx_ids for r in reviews if r.res_id == res_id):
                res_ids.append(res_id)
        return res_ids

    @api.model
    def _res_ids_from_my_completed_reviews(self):
        """Expedientes/SG donde el usuario aprobó o reenvió en cualquier etapa/fase."""
        user = self.env.user
        Review = self.env["tier.review"]
        closed_by_me = Review.search(
            [
                ("model", "=", self._name),
                ("done_by", "=", user.id),
                ("status", "in", list(_TIER_DONE_STATUSES)),
            ]
        )
        # Respaldo: aprobación sin done_by pero el usuario figuraba como revisor.
        approved_as_reviewer = Review.search(
            [
                ("model", "=", self._name),
                ("reviewer_ids", "in", user.id),
                ("status", "=", "approved"),
                ("done_by", "=", False),
            ]
        )
        return list(set(closed_by_me.mapped("res_id") + approved_as_reviewer.mapped("res_id")))

    @api.model
    def _search_tier_approval_pending_mine(self, operator, value):
        if operator != "=" or not value:
            return [("id", "=", False)]
        return [("can_review", "=", True)]

    @api.model
    def _search_tier_approval_done_mine(self, operator, value):
        if operator != "=" or not value:
            return [("id", "=", False)]
        return [("id", "in", self._res_ids_from_my_completed_reviews())]

    @api.model
    def _search_tier_approval_pending_all(self, operator, value):
        if operator != "=" or not value:
            return [("id", "=", False)]
        reviews = self.env["tier.review"].search(
            [
                ("model", "=", self._name),
                ("status", "in", list(_TIER_OPEN_STATUSES)),
            ]
        )
        return [("id", "in", self._res_ids_from_context_reviews(reviews))]

    @api.model
    def _search_tier_approval_done_all(self, operator, value):
        if operator != "=" or not value:
            return [("id", "=", False)]
        reviews = self.env["tier.review"].search(
            [
                ("model", "=", self._name),
                ("status", "in", list(_TIER_DONE_STATUSES)),
                ("done_by", "!=", False),
            ]
        )
        return [("id", "in", reviews.mapped("res_id"))]
