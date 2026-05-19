# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Si la línea no trae distribución analítica, intentamos inferirla
            # desde el expediente vinculado a la factura (directa o vía OC).
            if not vals.get("analytic_distribution"):
                inferred = self._infer_analytic_account_from_vals(vals)
                if inferred:
                    vals["analytic_distribution"] = {str(inferred.id): 100.0}
        return super().create(vals_list)

    def write(self, vals):
        if "analytic_distribution" not in vals:
            for line in self.filtered(lambda l: not l.display_type and not l.analytic_distribution):
                inferred = line._infer_analytic_account_from_move(line.move_id)
                if inferred:
                    vals = dict(vals, analytic_distribution={str(inferred.id): 100.0})
                    break
        return super().write(vals)

    def _infer_analytic_account_from_vals(self, vals):
        move = (
            self.env["account.move"].browse(vals.get("move_id"))
            if vals.get("move_id")
            else self.env["account.move"]
        )
        return self._infer_analytic_account_from_move(move)

    def _infer_analytic_account_from_move(self, move):
        if not move:
            return False
        if move.move_type not in ("in_invoice", "in_refund"):
            return False
        analytics = move.expedient_ids.mapped("analytic_account_id").filtered(lambda a: a)
        if not analytics:
            po_expedients = move.invoice_line_ids.purchase_line_id.order_id.mapped("expedient_ids")
            analytics = po_expedients.mapped("analytic_account_id").filtered(lambda a: a)
        if len(analytics) == 1:
            return analytics[0]
        return False
