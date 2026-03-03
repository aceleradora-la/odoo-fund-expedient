from odoo import fields, models, tools


class FundBudgetPositionReport(models.Model):
    _name = "fund.budget.position.report"
    _description = "Reporte de ejecución presupuestaria por partida"
    _auto = False
    _rec_name = "budget_position_id"
    _order = "fiscalyear desc, code"

    budget_id = fields.Many2one(
        "fund.budget",
        string="Presupuesto",
        readonly=True,
    )
    fiscalyear = fields.Char(
        string="Año",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        readonly=True,
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida",
        readonly=True,
    )
    parent_id = fields.Many2one(
        "fund.budget.position",
        string="Partida padre",
        readonly=True,
    )
    parent_path = fields.Char(readonly=True)
    category_id = fields.Many2one(
        "fund.budget.position.category",
        string="Categoría",
        readonly=True,
    )
    code = fields.Char(string="Código", readonly=True)
    name = fields.Char(string="Nombre", readonly=True)
    type = fields.Selection(
        [("normal", "Normal"), ("view", "Vista")],
        string="Tipo",
        readonly=True,
    )
    budget_assignment_allowed = fields.Boolean(
        string="Permite asignación",
        readonly=True,
    )
    amount_budget = fields.Monetary(
        string="Presupuesto",
        currency_field="currency_id",
        readonly=True,
    )
    amount_committed = fields.Monetary(
        string="Comprometido",
        currency_field="currency_id",
        readonly=True,
    )
    amount_real = fields.Monetary(
        string="Real",
        currency_field="currency_id",
        readonly=True,
    )
    amount_balance = fields.Monetary(
        string="Saldo",
        currency_field="currency_id",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH budget_initial AS (
                    SELECT
                        bl.budget_id,
                        bl.budget_position_id,
                        SUM(bl.initial_amount) AS amount
                    FROM fund_budget_line bl
                    GROUP BY bl.budget_id, bl.budget_position_id
                ),
                budget_adjustment AS (
                    SELECT
                        fa.budget_id,
                        fal.budget_position_id,
                        SUM(fal.amount) AS amount
                    FROM fund_budget_adjustment_line fal
                    JOIN fund_budget_adjustment fa ON fa.id = fal.adjustment_id
                    WHERE fa.state = 'posted'
                    GROUP BY fa.budget_id, fal.budget_position_id
                ),
                budget_leaf AS (
                    SELECT budget_id, budget_position_id, SUM(amount) AS amount_budget
                    FROM (
                        SELECT budget_id, budget_position_id, amount FROM budget_initial
                        UNION ALL
                        SELECT budget_id, budget_position_id, amount FROM budget_adjustment
                    ) x
                    GROUP BY budget_id, budget_position_id
                ),
                committed_leaf AS (
                    SELECT
                        b.id AS budget_id,
                        e.budget_position_id,
                        SUM(e.amount_committed) AS amount_committed
                    FROM fund_budget b
                    JOIN fund_expedient e
                        ON e.company_id = b.company_id
                       AND e.budget_position_id IS NOT NULL
                       AND e.request_date BETWEEN b.date_from AND b.date_to
                    GROUP BY b.id, e.budget_position_id
                ),
                real_leaf AS (
                    SELECT
                        b.id AS budget_id,
                        aml.budget_position_id,
                        SUM(aml.debit - aml.credit) AS amount_real
                    FROM fund_budget b
                    JOIN account_move_line aml
                        ON aml.company_id = b.company_id
                       AND aml.budget_position_id IS NOT NULL
                       AND aml.date BETWEEN b.date_from AND b.date_to
                       AND (aml.display_type IS NULL OR aml.display_type = '')
                    JOIN account_move am
                        ON am.id = aml.move_id
                       AND am.state = 'posted'
                    JOIN account_account aa ON aa.id = aml.account_id
                    JOIN account_account_type aat
                        ON aat.id = aa.user_type_id
                       AND aat.type IN ('expense', 'expense_depreciation')
                    GROUP BY b.id, aml.budget_position_id
                )
                SELECT
                    ((b.id::bigint << 32) + p.id::bigint) AS id,
                    b.id AS budget_id,
                    b.fiscalyear,
                    b.company_id,
                    rc.currency_id,
                    p.id AS budget_position_id,
                    p.parent_id,
                    p.parent_path,
                    p.category_id,
                    p.code,
                    p.name,
                    p.type,
                    p.budget_assignment_allowed,
                    COALESCE(SUM(bl.amount_budget), 0.0) AS amount_budget,
                    COALESCE(SUM(cl.amount_committed), 0.0) AS amount_committed,
                    COALESCE(SUM(rl.amount_real), 0.0) AS amount_real,
                    COALESCE(SUM(bl.amount_budget), 0.0)
                        - COALESCE(SUM(cl.amount_committed), 0.0)
                        - COALESCE(SUM(rl.amount_real), 0.0) AS amount_balance
                FROM fund_budget b
                JOIN res_company rc ON rc.id = b.company_id
                JOIN fund_budget_position p ON p.company_id = b.company_id
                LEFT JOIN fund_budget_position d
                    ON d.company_id = p.company_id
                   AND (
                        d.id = p.id
                        OR (
                            p.parent_path IS NOT NULL
                            AND d.parent_path LIKE (p.parent_path || '%')
                        )
                   )
                LEFT JOIN budget_leaf bl
                    ON bl.budget_id = b.id
                   AND bl.budget_position_id = d.id
                LEFT JOIN committed_leaf cl
                    ON cl.budget_id = b.id
                   AND cl.budget_position_id = d.id
                LEFT JOIN real_leaf rl
                    ON rl.budget_id = b.id
                   AND rl.budget_position_id = d.id
                GROUP BY
                    b.id,
                    b.fiscalyear,
                    b.company_id,
                    rc.currency_id,
                    p.id,
                    p.parent_id,
                    p.parent_path,
                    p.category_id,
                    p.code,
                    p.name,
                    p.type,
                    p.budget_assignment_allowed
            )
            """
        )
