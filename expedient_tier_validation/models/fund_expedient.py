# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _
from odoo.exceptions import UserError
from odoo import models


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "tier.validation"]
    _state_from = ["draft", "in_progress", "to_approve"]
    _state_to = ["approved"]
    _cancel_state = "cancel"
    _tier_validation_manual_config = False

    def action_next_stage(self):
        """No permitir pasar a la siguiente etapa hasta que la validación esté finalizada."""
        for rec in self:
            if rec.need_validation and rec.validation_status != "validated":
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
            rec.stage_id = target
        return True
