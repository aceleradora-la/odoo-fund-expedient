# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import AccessError


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "tier.validation.portal.mixin"]

    @api.model
    def _portal_access_clauses(self, user):
        """Los revisores también ven el expediente (cualquier etapa, historial incluido).

        Misma cláusula que la regla de registro `fund_expedient_portal_reviewer_rule`.
        """
        clauses = super()._portal_access_clauses(user)
        clauses.append(("review_ids.reviewer_ids", "in", [user.id]))
        return clauses

    def _portal_stage_nav_values(self):
        """Misma condición extra que la cabecera del backend: con una validación
        de la etapa en curso o rechazada no se avanza."""
        values = super()._portal_stage_nav_values()
        if values["portal_can_next"] and self.stage_validation_status in (
            "waiting",
            "pending",
            "rejected",
        ):
            values["portal_can_next"] = False
            values["portal_block_next"] = (
                _("La validación de esta etapa fue rechazada; reiníciela para continuar.")
                if self.stage_validation_status == "rejected"
                else _("Hay una validación de la etapa en curso.")
            )
        return values

    def _portal_tier_check_access(self):
        self.ensure_one()
        if not self._portal_user_can_access():
            raise AccessError(_("No tiene acceso a este expediente."))

    def _portal_tier_can_drive_flow(self):
        return self.can_edit_in_stage
