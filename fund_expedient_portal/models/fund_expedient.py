# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.osv import expression


class FundExpedient(models.Model):
    _inherit = ["fund.expedient", "portal.mixin"]

    @api.depends("id")
    def _compute_access_url(self):
        for rec in self:
            rec.access_url = f"/my/expedients/{rec.id}"

    @api.model
    def _portal_expedient_base_domain(self):
        """Dominio de visibilidad en portal: solicitante, asignado, revisor o partner."""
        user = self.env.user
        if user._is_public():
            return [("id", "=", False)]

        company_domain = [("company_id", "in", user.company_ids.ids + [False])]

        if user.has_group("base.group_portal") and not user.has_group("base.group_user"):
            partner = user.partner_id.commercial_partner_id
            access_domain = [
                "|",
                "|",
                ("message_partner_ids", "child_of", partner.ids),
                ("recommended_supplier_ids", "child_of", partner.ids),
                ("review_ids.reviewer_ids", "=", user.id),
            ]
            return expression.AND([company_domain, access_domain])

        access_domain = [
            "|",
            "|",
            ("requestor_id.user_id", "=", user.id),
            ("assignable_user_ids", "in", user.id),
            ("review_ids.reviewer_ids", "=", user.id),
        ]
        return expression.AND([company_domain, access_domain])

    def _portal_user_can_access(self):
        """True si el usuario puede ver el expediente en portal."""
        self.ensure_one()
        user = self.env.user
        if user._is_public():
            return False
        if user.has_group("fund_expedient.group_fund_expedient_manager"):
            return True

        if user.has_group("base.group_portal") and not user.has_group("base.group_user"):
            partner = user.partner_id.commercial_partner_id
            if partner in self.message_partner_ids:
                return True
            if partner in self.recommended_supplier_ids:
                return True
            if user in self.review_ids.reviewer_ids:
                return True
            return False

        if self.requestor_id.user_id == user:
            return True
        if user in self.assignable_user_ids:
            return True
        if user in self.review_ids.reviewer_ids:
            return True
        return False

    def _portal_can_advance_stage(self):
        """Puede intentar siguiente/anterior etapa desde portal (solo usuarios internos)."""
        self.ensure_one()
        user = self.env.user
        if user.has_group("base.group_portal") and not user.has_group("base.group_user"):
            return False
        return bool(self.can_edit_in_stage)
