# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ExpedientAssignWizard(models.TransientModel):
    """Asignar el expediente a un usuario del pool de la etapa actual.

    Lo abren el responsable actual o un Administrador (ver
    `fund.expedient.can_manage_responsible`): son los únicos que pueden
    reasignar un expediente que ya tiene responsable.
    """

    _name = "fund.expedient.assign.wizard"
    _description = "Asignar responsable del expediente"

    expedient_id = fields.Many2one(
        "fund.expedient",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    allowed_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_allowed_user_ids",
        string="Usuarios de la etapa",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        required=True,
        domain="[('id', 'in', allowed_user_ids)]",
    )
    note = fields.Char(string="Motivo", help="Queda registrado en el chatter del expediente.")

    @api.depends("expedient_id")
    def _compute_allowed_user_ids(self):
        for wizard in self:
            wizard.allowed_user_ids = wizard.expedient_id._responsible_candidates()

    def action_assign(self):
        self.ensure_one()
        if self.user_id not in self.allowed_user_ids:
            raise UserError(
                _("%s no puede operar la etapa «%s».")
                % (self.user_id.name, self.expedient_id.stage_id.name or "")
            )
        self.expedient_id._set_responsible(self.user_id, note=self.note)
        return {"type": "ir.actions.act_window_close"}
