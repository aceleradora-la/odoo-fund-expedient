# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundExpedientSpendRequest(models.Model):
    _name = "fund.expedient.spend.request"
    # El mixin debe ir ANTES que "tier.validation" en _inherit: por C3 linearization, los
    # métodos del mixin (validate_tier, request_validation, restart_validation, etc.) ganan
    # sobre los del base OCA. Sin esto, el botón Aprobar marca la review pero NO ejecuta
    # _on_context_tier_validated y la fase nunca pasa a "approved".
    _inherit = ["fund.expedient.spend.request", "mail.thread", "fund.tier.validation.mixin", "tier.validation"]

    # Manual: insertamos los botones/etiquetas tier explícitamente en el form (standalone y embebido),
    # porque el SG no tiene <header> nativo y el embedded view no pasa por get_view de SG.
    _tier_validation_manual_config = True
    _state_field = "tier_validation_state"
    _state_from = ["generated"]
    _state_to = ["approved"]
    _cancel_state = False

    tier_validation_state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("generated", "Generada"),
            ("approved", "Aprobada"),
        ],
        string="Estado validación",
        compute="_compute_tier_validation_state",
        store=True,
    )

    @api.depends(
        "preventiva_state",
        "definitiva_state",
        "spend_state",
        "review_ids",
        "review_ids.status",
        "review_ids.spend_phase",
    )
    def _compute_tier_validation_state(self):
        """Computa el estado tier y regulariza la fase si está validada por completo.

        Side effect deliberado: si todas las reviews del contexto activo están aprobadas
        pero la fase aún quedó en "generated" (caso típico: aprobación realizada por
        wizard de comentarios o con un orden de _inherit antiguo donde el hook no
        corrió), marcamos la fase como "approved" automáticamente. Esto evita tener
        que reiniciar y re-aprobar la validación manualmente.
        """
        for rec in self:
            phase = rec._get_active_spend_phase()
            if rec.has_stage_reviews and rec.stage_validation_status == "validated":
                current_state = (
                    rec.preventiva_state if phase == "preventiva" else rec.definitiva_state
                )
                if current_state == "generated":
                    rec.with_context(skip_validation_check=True)._mark_phase_approved(phase)
            phase_state = (
                rec.preventiva_state if phase == "preventiva" else rec.definitiva_state
            )
            if phase_state == "approved":
                rec.tier_validation_state = "approved"
            elif phase_state == "generated":
                rec.tier_validation_state = "generated"
            else:
                rec.tier_validation_state = "draft"

    def _tier_review_context_field(self):
        return "spend_phase"

    def _get_active_spend_phase(self):
        self.ensure_one()
        if self.spend_state == "definitiva" or self.definitiva_state in ("generated", "approved"):
            return "definitiva"
        return "preventiva"

    def _tier_context_value(self):
        return self._get_active_spend_phase()

    def _check_state_from_condition(self):
        self.ensure_one()
        phase = self._get_active_spend_phase()
        if phase == "preventiva":
            return self.preventiva_state == "generated"
        return self.definitiva_state == "generated"

    def _get_company(self):
        if not self:
            return self.env.company
        return self[:1].company_id or self.env.company

    def _on_context_tier_validated(self):
        # skip_validation_check: el guard de base_tier_validation bloquea cualquier
        # write distinto a "Followers" mientras hay tier activo. Aquí estamos completando
        # el flujo desde dentro (todas las reviews del contexto están aprobadas), por lo
        # que es seguro saltar el chequeo para persistir preventiva/definitiva = approved.
        for rec in self:
            if rec._is_context_tier_complete():
                rec.with_context(skip_validation_check=True)._mark_phase_approved(
                    rec._get_active_spend_phase()
                )

    def action_generate_preventiva(self):
        res = super().action_generate_preventiva()
        for rec in self:
            if not rec._get_applicable_tier_definitions():
                rec.preventiva_state = "approved"
        return res

    def action_generate_final(self):
        res = super().action_generate_final()
        for rec in self:
            if not rec._get_applicable_tier_definitions():
                rec.definitiva_state = "approved"
        return res
