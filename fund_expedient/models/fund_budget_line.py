from odoo import api, fields, models


class FundBudgetLine(models.Model):
    _name = "fund.budget.line"
    _description = "Línea de presupuesto"
    _order = "budget_position_id"

    budget_id = fields.Many2one(
        "fund.budget",
        string="Presupuesto",
        required=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        related="budget_id.state",
        string="Estado",
        store=True,
    )
    company_id = fields.Many2one(
        related="budget_id.company_id",
        string="Compañía",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="budget_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria",
        required=True,
        domain="[('budget_assignment_allowed', '=', True), ('company_id', '=', company_id)]",
    )
    initial_amount = fields.Monetary(
        string="Presupuesto inicial",
        required=True,
        currency_field="currency_id",
    )
    adjustment_amount = fields.Monetary(
        string="Ajustes",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_total = fields.Monetary(
        string="Presupuesto vigente",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    committed_amount = fields.Monetary(
        string="Comprometido",
        compute="_compute_execution_amounts",
        store=False,
        currency_field="currency_id",
    )
    real_amount = fields.Monetary(
        string="Real",
        compute="_compute_execution_amounts",
        store=False,
        currency_field="currency_id",
    )
    balance_amount = fields.Monetary(
        string="Saldo",
        compute="_compute_execution_amounts",
        store=False,
        currency_field="currency_id",
    )

    _sql_constraints = [
        (
            "budget_line_unique_position",
            "unique(budget_id, budget_position_id)",
            "La partida presupuestaria debe ser única dentro del presupuesto.",
        ),
    ]

    @api.depends(
        "initial_amount",
        "budget_id.adjustment_ids.state",
        "budget_id.adjustment_ids.line_ids.amount",
        "budget_id.adjustment_ids.line_ids.budget_position_id",
    )
    def _compute_amounts(self):
        for rec in self:
            posted_lines = rec.budget_id.adjustment_ids.filtered(
                lambda a: a.state == "posted"
            ).mapped("line_ids")
            rec.adjustment_amount = sum(
                posted_lines.filtered(
                    lambda l: l.budget_position_id == rec.budget_position_id
                ).mapped("amount")
            )
            rec.amount_total = rec.initial_amount + rec.adjustment_amount

    def _compute_execution_amounts(self):
        Report = self.env["fund.budget.position.report"].sudo()
        for rec in self:
            data = Report.search(
                [
                    ("budget_id", "=", rec.budget_id.id),
                    ("budget_position_id", "=", rec.budget_position_id.id),
                ],
                limit=1,
            )
            rec.committed_amount = data.amount_committed if data else 0.0
            rec.real_amount = data.amount_real if data else 0.0
            rec.balance_amount = data.amount_balance if data else rec.amount_total
