from odoo import fields, models, tools


class FundBudgetAnalyticReport(models.Model):
    _name = "fund.budget.analytic.report"
    _description = "Reporte de ejecución presupuestaria por cuenta analítica"
    _auto = False
    _rec_name = "analytic_account_id"
    _order = "fiscalyear desc, month, analytic_account_id"

    budget_id = fields.Many2one("fund.budget", string="Presupuesto", readonly=True)
    fiscalyear = fields.Char(string="Año", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        readonly=True,
    )
    month = fields.Integer(
        string="Mes",
        readonly=True,
        help="0 = Total año; 1..12 = Ene..Dic",
    )
    amount_budget = fields.Monetary(string="Presupuesto", currency_field="currency_id", readonly=True)
    amount_committed = fields.Monetary(string="Comprometido", currency_field="currency_id", readonly=True)
    amount_real = fields.Monetary(string="Real", currency_field="currency_id", readonly=True)
    amount_balance = fields.Monetary(string="Saldo", currency_field="currency_id", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH months AS (
                    SELECT 0 AS month
                    UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
                    UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6
                    UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
                    UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12
                ),
                budget_monthly AS (
                    SELECT
                        bl.budget_id,
                        bl.analytic_account_id,
                        m.month,
                        SUM(
                            CASE m.month
                                WHEN 0 THEN bl.amount_total
                                WHEN 1 THEN bl.m01
                                WHEN 2 THEN bl.m02
                                WHEN 3 THEN bl.m03
                                WHEN 4 THEN bl.m04
                                WHEN 5 THEN bl.m05
                                WHEN 6 THEN bl.m06
                                WHEN 7 THEN bl.m07
                                WHEN 8 THEN bl.m08
                                WHEN 9 THEN bl.m09
                                WHEN 10 THEN bl.m10
                                WHEN 11 THEN bl.m11
                                WHEN 12 THEN bl.m12
                                ELSE 0.0
                            END
                        ) AS amount_budget
                    FROM fund_budget_line bl
                    JOIN months m ON TRUE
                    GROUP BY bl.budget_id, bl.analytic_account_id, m.month
                ),
                committed_monthly AS (
                    SELECT
                        b.id AS budget_id,
                        e.analytic_account_id,
                        0 AS month,
                        SUM(e.amount_committed * CASE WHEN e.operation_type = 'income' THEN -1 ELSE 1 END) AS amount_committed
                    FROM fund_budget b
                    JOIN fund_expedient e
                        ON e.company_id = b.company_id
                       AND e.analytic_account_id IS NOT NULL
                       AND e.request_date BETWEEN b.date_from AND b.date_to
                    GROUP BY b.id, e.analytic_account_id
                    UNION ALL
                    SELECT
                        b.id AS budget_id,
                        e.analytic_account_id,
                        EXTRACT(MONTH FROM e.request_date)::int AS month,
                        SUM(e.amount_committed * CASE WHEN e.operation_type = 'income' THEN -1 ELSE 1 END) AS amount_committed
                    FROM fund_budget b
                    JOIN fund_expedient e
                        ON e.company_id = b.company_id
                       AND e.analytic_account_id IS NOT NULL
                       AND e.request_date BETWEEN b.date_from AND b.date_to
                    GROUP BY b.id, e.analytic_account_id, EXTRACT(MONTH FROM e.request_date)
                ),
                real_monthly AS (
                    SELECT
                        b.id AS budget_id,
                        e.analytic_account_id,
                        0 AS month,
                        SUM(e.amount_real * CASE WHEN e.operation_type = 'income' THEN -1 ELSE 1 END) AS amount_real
                    FROM fund_budget b
                    JOIN fund_expedient e
                        ON e.company_id = b.company_id
                       AND e.analytic_account_id IS NOT NULL
                       AND e.request_date BETWEEN b.date_from AND b.date_to
                    GROUP BY b.id, e.analytic_account_id
                    UNION ALL
                    SELECT
                        b.id AS budget_id,
                        e.analytic_account_id,
                        EXTRACT(MONTH FROM e.request_date)::int AS month,
                        SUM(e.amount_real * CASE WHEN e.operation_type = 'income' THEN -1 ELSE 1 END) AS amount_real
                    FROM fund_budget b
                    JOIN fund_expedient e
                        ON e.company_id = b.company_id
                       AND e.analytic_account_id IS NOT NULL
                       AND e.request_date BETWEEN b.date_from AND b.date_to
                    GROUP BY b.id, e.analytic_account_id, EXTRACT(MONTH FROM e.request_date)
                )
                SELECT
                    ((b.id::bigint << 32) + (aa.id::bigint << 6) + m.month::bigint) AS id,
                    b.id AS budget_id,
                    b.fiscalyear,
                    b.company_id,
                    rc.currency_id,
                    aa.id AS analytic_account_id,
                    m.month,
                    COALESCE(bm.amount_budget, 0.0) AS amount_budget,
                    COALESCE(cm.amount_committed, 0.0) AS amount_committed,
                    COALESCE(rm.amount_real, 0.0) AS amount_real,
                    COALESCE(bm.amount_budget, 0.0)
                        - COALESCE(cm.amount_committed, 0.0)
                        - COALESCE(rm.amount_real, 0.0) AS amount_balance
                FROM fund_budget b
                JOIN res_company rc ON rc.id = b.company_id
                JOIN fund_budget_line bl ON bl.budget_id = b.id
                JOIN account_analytic_account aa ON aa.id = bl.analytic_account_id
                JOIN months m ON TRUE
                LEFT JOIN budget_monthly bm
                    ON bm.budget_id = b.id
                   AND bm.analytic_account_id = aa.id
                   AND bm.month = m.month
                LEFT JOIN committed_monthly cm
                    ON cm.budget_id = b.id
                   AND cm.analytic_account_id = aa.id
                   AND cm.month = m.month
                LEFT JOIN real_monthly rm
                    ON rm.budget_id = b.id
                   AND rm.analytic_account_id = aa.id
                   AND rm.month = m.month
            )
            """
        )

