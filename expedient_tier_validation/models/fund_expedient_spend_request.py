# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundExpedientSpendRequest(models.Model):
    _name = "fund.expedient.spend.request"
    _inherit = ["fund.expedient.spend.request", "mail.thread", "tier.validation", "fund.tier.validation.mixin"]

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
    )
    def _compute_tier_validation_state(self):
        for rec in self:
            phase = rec._get_active_spend_phase()
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
        for rec in self:
            if rec._is_context_tier_complete():
                rec._mark_phase_approved(rec._get_active_spend_phase())

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
