# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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

    def write(self, vals):
        res = super().write(vals)
        if any(
            f in vals
            for f in ("expedient_ids", "state", "amount_total", "currency_id")
        ):
            expedients = self.mapped("expedient_ids")
            if expedients:
                expedients.invalidate_recordset(
                    ["amount_real", "amount_real_uf"]
                )
        return res
