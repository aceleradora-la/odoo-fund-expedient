# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.osv import expression


class FundExpedient(models.Model):
    # Odoo 18: al extender un modelo ya definido con _name en otro módulo
    # (p. ej. expedient_tier_validation), hay que repetir _name aquí para
    # evitar duplicar campos Many2many al mezclar mixins.
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "portal.mixin"]

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/expedients/{rec.id}"

    @api.model
    def _portal_has_tier_reviews(self):
        """True si tier validation está instalado (campo review_ids disponible)."""
        return "review_ids" in self._fields

    @api.model
    def _portal_or_domain(self, clauses):
        """Construye dominio OR a partir de tuplas (campo, operador, valor)."""
        clauses = [c for c in clauses if c]
        if not clauses:
            return [("id", "=", False)]
        if len(clauses) == 1:
            return [clauses[0]]
        domain = ["|"] * (len(clauses) - 1)
        domain.extend(clauses)
        return domain

    @api.model
    def _portal_expedient_base_domain(self):
        """Dominio de visibilidad en portal: solicitante, asignado, revisor o partner."""
        user = self.env.user
        if user._is_public():
            return [("id", "=", False)]

        company_domain = [("company_id", "in", user.company_ids.ids + [False])]

        if user.has_group("base.group_portal") and not user.has_group("base.group_user"):
            partner = user.partner_id.commercial_partner_id
            clauses = [
                ("message_partner_ids", "child_of", partner.ids),
                ("recommended_supplier_ids", "child_of", partner.ids),
            ]
            if self._portal_has_tier_reviews():
                clauses.append(("review_ids.reviewer_ids", "=", user.id))
            access_domain = self._portal_or_domain(clauses)
            return expression.AND([company_domain, access_domain])

        clauses = [
            ("requestor_id.user_id", "=", user.id),
            ("assignable_user_ids", "in", user.id),
        ]
        if self._portal_has_tier_reviews():
            clauses.append(("review_ids.reviewer_ids", "=", user.id))
        access_domain = self._portal_or_domain(clauses)
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
            if self._portal_has_tier_reviews() and user in self.review_ids.reviewer_ids:
                return True
            return False

        if self.requestor_id.user_id == user:
            return True
        if user in self.assignable_user_ids:
            return True
        if self._portal_has_tier_reviews() and user in self.review_ids.reviewer_ids:
            return True
        return False

    def _portal_is_internal_user(self):
        user = self.env.user
        return not (
            user.has_group("base.group_portal")
            and not user.has_group("base.group_user")
        )

    def _portal_allowed_stages(self):
        self.ensure_one()
        for _rec, stages in self._get_allowed_stages():
            return stages
        return self.env["fund.expedient.stage"]

    def _portal_current_stage_index(self, stages):
        self.ensure_one()
        if not self.stage_id or not stages:
            return -1
        stage_ids = stages.ids
        if self.stage_id.id not in stage_ids:
            return -1
        return stage_ids.index(self.stage_id.id)

    def _portal_tier_blocks_stage_change(self):
        """True si tier validation impide cambiar de etapa (misma regla que backend)."""
        self.ensure_one()
        if not hasattr(self, "_current_stage_reviews"):
            return False
        reviews = self._current_stage_reviews()
        return bool(
            reviews.filtered(lambda r: r.status in ("waiting", "pending", "rejected"))
        )

    def _portal_tier_block_reason_next(self):
        self.ensure_one()
        if self._portal_tier_blocks_stage_change():
            return _(
                "Complete la validación de la etapa actual antes de avanzar."
            )
        if not hasattr(self, "_get_applicable_tier_definitions"):
            return ""
        applicable = self._get_applicable_tier_definitions()
        if not applicable or not hasattr(self, "_is_current_stage_tier_complete"):
            return ""
        if self._is_current_stage_tier_complete():
            return ""
        if (
            hasattr(self, "_missing_tier_reviews_for_current_stage")
            and self._missing_tier_reviews_for_current_stage()
        ):
            return _(
                "Solicite la validación y espere su aprobación antes de avanzar."
            )
        return _("Complete la validación antes de avanzar.")

    def _portal_spend_request_block_reason_next(self):
        self.ensure_one()
        if not self.stage_id:
            return ""
        mode = self.stage_id.spend_request_mode
        if mode not in ("preventiva", "final"):
            return ""
        sr = self.spend_request_ids[:1]
        if not sr:
            return _(
                "Debe generar la Solicitud de Gasto antes de salir de esta etapa."
            )
        if mode == "preventiva":
            if not sr.is_phase_generated("preventiva"):
                return _(
                    "Debe generar la Solicitud de Gasto preventiva antes de avanzar."
                )
            if not sr.is_phase_approved("preventiva"):
                return _(
                    "La Solicitud de Gasto preventiva debe estar aprobada antes de avanzar."
                )
        if mode == "final":
            if not sr.is_phase_generated("definitiva"):
                return _(
                    "Debe generar la Solicitud de Gasto definitiva antes de avanzar."
                )
            if not sr.is_phase_approved("definitiva"):
                return _(
                    "La Solicitud de Gasto definitiva debe estar aprobada antes de avanzar."
                )
        return ""

    def _portal_stage_nav_values(self):
        """Valores QWeb para botones etapa anterior / siguiente en portal."""
        self.ensure_one()
        values = {
            "portal_stage_show_panel": False,
            "portal_can_previous": False,
            "portal_can_next": False,
            "portal_block_previous": "",
            "portal_block_next": "",
        }
        if not self._portal_is_internal_user():
            return values

        values["portal_stage_show_panel"] = True

        if self.state == "cancel":
            msg = _("El expediente está cancelado.")
            values["portal_block_previous"] = msg
            values["portal_block_next"] = msg
            return values

        if not self.can_edit_in_stage:
            msg = _(
                "No está asignado a la etapa actual; solo quienes operan "
                "esta etapa pueden cambiarla."
            )
            values["portal_block_previous"] = msg
            values["portal_block_next"] = msg
            return values

        stages = self._portal_allowed_stages()
        index = self._portal_current_stage_index(stages)
        assign = self._current_stage_assign()

        if self._portal_tier_blocks_stage_change():
            tier_msg = _(
                "Hay validaciones pendientes o rechazadas en esta etapa."
            )
            values["portal_block_previous"] = tier_msg
            values["portal_block_next"] = tier_msg
            return values

        doc_block = self._portal_required_documents_block_reason_leave()
        if doc_block:
            values["portal_block_previous"] = doc_block
            values["portal_block_next"] = doc_block
            return values

        if index <= 0:
            values["portal_block_previous"] = _("Ya está en la primera etapa.")
        else:
            values["portal_can_previous"] = True

        if assign and assign.is_final_stage:
            values["portal_block_next"] = _(
                "Esta es una etapa final del flujo; no puede avanzar."
            )
            return values

        if index < 0 or index + 1 >= len(stages):
            values["portal_block_next"] = _("Ya está en la última etapa del flujo.")
            return values

        tier_reason = self._portal_tier_block_reason_next()
        if tier_reason:
            values["portal_block_next"] = tier_reason
            return values

        if index == 0 and not (self.amount_estimated and self.amount_estimated > 0):
            values["portal_block_next"] = _(
                "Debe cargar un monto estimado mayor a cero antes de avanzar "
                "desde la primera etapa."
            )
            return values

        if assign and assign.require_notification and not self._notification_stage_satisfied():
            values["portal_block_next"] = _(
                "Debe notificar a los oferentes antes de avanzar "
                "(use «Notificar oferentes» en el expediente del backend)."
            )
            return values

        sg_reason = self._portal_spend_request_block_reason_next()
        if sg_reason:
            values["portal_block_next"] = sg_reason
            return values

        values["portal_can_next"] = True
        return values

    def _portal_required_documents_block_reason_leave(self):
        self.ensure_one()
        assign = self._current_stage_assign()
        if not assign:
            return ""
        if assign.require_technical_spec_document:
            tech_docs = self.document_ids.filtered(
                lambda doc: doc.is_technical_spec and doc.file_data
            )
            if not tech_docs:
                return _(
                    "Debe adjuntar al menos un documento de Especificación técnica "
                    "con archivo antes de cambiar de etapa."
                )
        if assign.require_particular_conditions_document:
            cond_docs = self.document_ids.filtered(
                lambda doc: doc.is_particular_conditions and doc.file_data
            )
            if not cond_docs:
                return _(
                    "Debe adjuntar al menos un documento de Condiciones particulares "
                    "con archivo antes de cambiar de etapa."
                )
        return ""

    def _portal_can_advance_stage(self):
        """Compat: True si puede usar al menos una acción de etapa."""
        nav = self._portal_stage_nav_values()
        return nav["portal_can_previous"] or nav["portal_can_next"]
