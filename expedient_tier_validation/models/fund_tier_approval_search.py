# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

_TIER_DONE_STATUSES = ("approved", "forwarded")
_TIER_OPEN_STATUSES = ("pending", "waiting")


class FundTierApprovalSearchMixin(models.AbstractModel):
    """Campos de búsqueda para el menú Mis aprobaciones (pendientes, historial, vista admin)."""

    _name = "fund.tier.approval.search.mixin"
    _description = "Búsquedas Mis aprobaciones (tier)"

    tier_done_by_user_ids = fields.Many2many(
        comodel_name="res.users",
        string="Usuarios que cerraron validaciones",
        compute="_compute_tier_done_by_user_ids",
        search="_search_tier_done_by_user_ids",
        help="Usuarios en done_by de tier.review aprobadas o reenviadas (cualquier etapa/fase).",
    )
    tier_approval_pending_mine = fields.Boolean(search="_search_tier_approval_pending_mine")
    tier_approval_pending_all = fields.Boolean(search="_search_tier_approval_pending_all")

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
    def _res_ids_closed_by_users(self, user_ids=None, *, any_user=False):
        """IDs de registros con tier.review cerrada (cualquier etapa/fase)."""
        domain = [
            ("model", "=", self._name),
            ("status", "in", list(_TIER_DONE_STATUSES)),
            ("res_id", "!=", False),
        ]
        if any_user:
            domain.append(("done_by", "!=", False))
        elif user_ids:
            domain.append(("done_by", "in", list(user_ids)))
        else:
            return []
        reviews = self.env["tier.review"].sudo().search(domain)
        return list(set(reviews.mapped("res_id")))

    @api.depends("review_ids.done_by", "review_ids.status")
    def _compute_tier_done_by_user_ids(self):
        for rec in self:
            rec.tier_done_by_user_ids = rec.review_ids.filtered(
                lambda r: r.status in _TIER_DONE_STATUSES and r.done_by
            ).mapped("done_by")

    @api.model
    def _search_tier_done_by_user_ids(self, operator, value):
        if operator == "=":
            user_ids = [value] if value else []
        elif operator == "in":
            user_ids = list(value) if value else []
        elif operator == "!=":
            if not value:
                return [("id", "in", self._res_ids_closed_by_users(any_user=True))]
            all_closed = set(self._res_ids_closed_by_users(any_user=True))
            by_user = set(self._res_ids_closed_by_users([value]))
            return [("id", "in", list(all_closed - by_user))]
        else:
            return [("id", "=", False)]
        if not user_ids:
            return [("id", "=", False)]
        return [("id", "in", self._res_ids_closed_by_users(user_ids))]

    @api.model
    def _search_tier_approval_pending_mine(self, operator, value):
        if operator != "=" or not value:
            return [("id", "=", False)]
        return [("can_review", "=", True)]

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
