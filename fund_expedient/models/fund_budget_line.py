from odoo import api, fields, models


class FundBudgetLine(models.Model):
    _name = "fund.budget.line"
    _description = "Línea de presupuesto"
    _order = "analytic_account_id"

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
    # Legacy (para migración/histórico). No se usa más en UI.
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria (legacy)",
        domain="[('budget_assignment_allowed', '=', True), ('company_id', '=', company_id)]",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        required=True,
        domain="[('company_id', 'in', [False, company_id])]",
    )
    m01 = fields.Monetary(string="Ene", currency_field="currency_id", required=True, default=0.0)
    m02 = fields.Monetary(string="Feb", currency_field="currency_id", required=True, default=0.0)
    m03 = fields.Monetary(string="Mar", currency_field="currency_id", required=True, default=0.0)
    m04 = fields.Monetary(string="Abr", currency_field="currency_id", required=True, default=0.0)
    m05 = fields.Monetary(string="May", currency_field="currency_id", required=True, default=0.0)
    m06 = fields.Monetary(string="Jun", currency_field="currency_id", required=True, default=0.0)
    m07 = fields.Monetary(string="Jul", currency_field="currency_id", required=True, default=0.0)
    m08 = fields.Monetary(string="Ago", currency_field="currency_id", required=True, default=0.0)
    m09 = fields.Monetary(string="Sep", currency_field="currency_id", required=True, default=0.0)
    m10 = fields.Monetary(string="Oct", currency_field="currency_id", required=True, default=0.0)
    m11 = fields.Monetary(string="Nov", currency_field="currency_id", required=True, default=0.0)
    m12 = fields.Monetary(string="Dic", currency_field="currency_id", required=True, default=0.0)
    amount_year = fields.Monetary(
        string="Presupuesto año",
        compute="_compute_amounts",
        store=True,
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
            "budget_line_unique_analytic",
            "unique(budget_id, analytic_account_id)",
            "La cuenta analítica debe ser única dentro del presupuesto.",
        ),
    ]

    @api.depends(
        "m01",
        "m02",
        "m03",
        "m04",
        "m05",
        "m06",
        "m07",
        "m08",
        "m09",
        "m10",
        "m11",
        "m12",
        "budget_id.adjustment_ids.state",
        "budget_id.adjustment_ids.line_ids.amount",
        "budget_id.adjustment_ids.line_ids.analytic_account_id",
    )
    def _compute_amounts(self):
        for rec in self:
            posted_lines = rec.budget_id.adjustment_ids.filtered(
                lambda a: a.state == "posted"
            ).mapped("line_ids")
            rec.adjustment_amount = sum(
                posted_lines.filtered(
                    lambda l: l.analytic_account_id == rec.analytic_account_id
                ).mapped("amount")
            )
            rec.amount_year = (
                rec.m01
                + rec.m02
                + rec.m03
                + rec.m04
                + rec.m05
                + rec.m06
                + rec.m07
                + rec.m08
                + rec.m09
                + rec.m10
                + rec.m11
                + rec.m12
            )
            rec.amount_total = rec.amount_year + rec.adjustment_amount

    def _compute_execution_amounts(self):
        Report = self.env["fund.budget.analytic.report"].sudo()
        for rec in self:
            data = Report.search(
                [
                    ("budget_id", "=", rec.budget_id.id),
                    ("analytic_account_id", "=", rec.analytic_account_id.id),
                    ("month", "=", 0),
                ],
                limit=1,
            )
            rec.committed_amount = data.amount_committed if data else 0.0
            rec.real_amount = data.amount_real if data else 0.0
            rec.balance_amount = data.amount_balance if data else rec.amount_total
