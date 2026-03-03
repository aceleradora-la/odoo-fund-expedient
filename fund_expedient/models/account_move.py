# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_account_move_rel",
        "move_id",
        "expedient_id",
        string="Expedientes",
        copy=False,
        help="Para facturas directas (sin orden de compra). "
        "Si la factura viene de una OC, la relación se toma de la orden.",
    )

    @api.onchange("expedient_ids")
    def _onchange_expedient_ids_budget_position(self):
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            positions = move.expedient_ids.mapped("budget_position_id").filtered(lambda p: p)
            if len(positions) == 1:
                position = positions[0]
                for line in move.invoice_line_ids.filtered(
                    lambda l: not l.display_type and not l.budget_position_id
                ):
                    line.budget_position_id = position

    def write(self, vals):
        res = super().write(vals)
        if "expedient_ids" in vals:
            for move in self:
                if move.move_type in ("in_invoice", "in_refund") and move.expedient_ids:
                    positions = move.expedient_ids.mapped("budget_position_id").filtered(lambda p: p)
                    if len(positions) == 1:
                        lines_to_update = move.invoice_line_ids.filtered(
                            lambda l: not l.display_type and not l.budget_position_id
                        )
                        if lines_to_update:
                            lines_to_update.write({"budget_position_id": positions[0].id})
        if any(
            f in vals
            for f in ("expedient_ids", "state", "amount_total", "currency_id", "invoice_line_ids")
        ):
            # Facturas directas: expedient_ids
            expedients = self.mapped("expedient_ids")
            # Facturas desde OC: expedientes vía líneas con purchase_line_id
            for move in self:
                if move.move_type in ("in_invoice", "in_refund"):
                    pos = move.invoice_line_ids.purchase_line_id.order_id
                    for po in pos:
                        if po.expedient_ids:
                            expedients |= po.expedient_ids
            if expedients:
                expedients.invalidate_recordset(
                    [
                        "amount_committed",
                        "amount_committed_uf",
                        "amount_real",
                        "amount_real_uf",
                    ]
                )
        return res
