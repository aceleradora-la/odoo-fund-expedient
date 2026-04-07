from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria",
        domain="[('budget_assignment_allowed', '=', True), ('company_id', '=', company_id)]",
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("budget_position_id"):
                inferred = self._infer_budget_position_from_vals(vals)
                if inferred:
                    vals["budget_position_id"] = inferred.id
            if not vals.get("analytic_distribution"):
                inferred = self._infer_analytic_account_from_vals(vals)
                if inferred:
                    vals["analytic_distribution"] = {str(inferred.id): 100.0}
        return super().create(vals_list)

    def write(self, vals):
        if "budget_position_id" not in vals:
            for line in self.filtered(
                lambda l: not l.budget_position_id and not l.display_type
            ):
                inferred = line._infer_budget_position_from_move(line.move_id)
                if inferred:
                    vals = dict(vals, budget_position_id=inferred.id)
                    break
        if "analytic_distribution" not in vals:
            for line in self.filtered(lambda l: not l.display_type and not l.analytic_distribution):
                inferred = line._infer_analytic_account_from_move(line.move_id)
                if inferred:
                    vals = dict(vals, analytic_distribution={str(inferred.id): 100.0})
                    break
        return super().write(vals)

    @api.constrains("budget_position_id")
    def _check_budget_position(self):
        for rec in self.filtered("budget_position_id"):
            if not rec.budget_position_id.budget_assignment_allowed:
                raise ValidationError(
                    _("Solo puede imputar movimientos a partidas que permitan asignación.")
                )

    def _infer_budget_position_from_vals(self, vals):
        move = self.env["account.move"].browse(vals.get("move_id")) if vals.get("move_id") else self.env["account.move"]
        return self._infer_budget_position_from_move(move)

    def _infer_analytic_account_from_vals(self, vals):
        move = (
            self.env["account.move"].browse(vals.get("move_id"))
            if vals.get("move_id")
            else self.env["account.move"]
        )
        return self._infer_analytic_account_from_move(move)

    def _infer_budget_position_from_move(self, move):
        if not move:
            return False
        if move.move_type not in ("in_invoice", "in_refund"):
            return False
        positions = move.expedient_ids.mapped("budget_position_id").filtered(lambda p: p)
        if not positions:
            po_expedients = move.invoice_line_ids.purchase_line_id.order_id.mapped("expedient_ids")
            positions = po_expedients.mapped("budget_position_id").filtered(lambda p: p)
        if len(positions) == 1:
            return positions[0]
        return False

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
