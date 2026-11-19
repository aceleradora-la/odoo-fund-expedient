# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ExpedientRelaunchWizard(models.TransientModel):
    """Iniciar un expediente nuevo a partir de uno cerrado sin adjudicar.

    Caso típico: una Compulsa abreviada cuyas ofertas superaron el tope se
    declara fracasada y el procedimiento sigue como Licitación. Ver
    `fund.expedient._relaunch_as`.
    """

    _name = "fund.expedient.relaunch.wizard"
    _description = "Iniciar nuevo expediente"

    expedient_id = fields.Many2one("fund.expedient", required=True, readonly=True)
    operation_type = fields.Selection(related="expedient_id.operation_type")
    current_type_id = fields.Many2one(related="expedient_id.type_id")
    type_id = fields.Many2one(
        "fund.expedient.type",
        string="Tipo del expediente nuevo",
        required=True,
        domain="[('operation_type', '=', operation_type), ('id', '!=', current_type_id)]",
    )
    over_limit_warning = fields.Char(compute="_compute_over_limit_warning")

    @api.depends("type_id", "expedient_id")
    def _compute_over_limit_warning(self):
        for wizard in self:
            exp = wizard.expedient_id
            limit = wizard.type_id.max_amount_unit
            total = exp.amount_estimated_confirmed_unit or exp.amount_estimated_unit
            wizard.over_limit_warning = (
                _(
                    "El total del expediente también supera el monto máximo de «%s»."
                )
                % wizard.type_id.name
                if limit and total and total > limit
                else False
            )

    def action_confirm(self):
        self.ensure_one()
        new = self.expedient_id._relaunch_as(self.type_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Expediente"),
            "res_model": "fund.expedient",
            "res_id": new.id,
            "view_mode": "form",
            "target": "current",
        }
