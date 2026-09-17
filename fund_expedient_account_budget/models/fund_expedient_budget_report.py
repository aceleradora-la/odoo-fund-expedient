# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models, tools

from odoo.addons.fund_expedient.hooks import _column_exists

# Estados del presupuesto de Contabilidad que NO se comparan. Se comparan
# todos los demás, borradores incluidos: puede haber varias versiones y el
# usuario elige contra cuál mirar.
EXCLUDED_BUDGET_STATES = ("canceled", "cancelled", "cancel")


class FundExpedientBudgetReport(models.Model):
    """Ejecución presupuestaria: presupuesto de Contabilidad vs. expedientes.

    Vista SQL con una fila por línea de presupuesto (`budget.line`) de
    Contabilidad. El presupuesto sale de ahí; el comprometido y el real salen
    de los expedientes que llevan la misma cuenta analítica, del mismo tipo
    de operación (gasto o ingreso) y cuya fecha de solicitud cae en el
    período del presupuesto. Ambos importes ya están calculados y
    almacenados en cada expediente, en moneda de la compañía.

    Reemplaza al reporte sobre los presupuestos propios de Expedientes
    (`fund.budget`), que dejan de usarse.
    """

    _name = "fund.expedient.budget.report"
    _description = "Ejecución presupuestaria por cuenta analítica"
    _auto = False
    _rec_name = "analytic_account_id"
    _order = "budget_analytic_id desc, analytic_account_id"

    budget_analytic_id = fields.Many2one("budget.analytic", string="Presupuesto", readonly=True)
    budget_state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("confirmed", "Abierto"),
            ("revised", "Revisado"),
            ("done", "Hecho"),
        ],
        string="Estado del presupuesto",
        readonly=True,
    )
    budget_type = fields.Selection(
        selection=[("expense", "Gasto"), ("revenue", "Ingreso"), ("both", "Ambos")],
        string="Tipo de presupuesto",
        readonly=True,
    )
    date_from = fields.Date(string="Desde", readonly=True)
    date_to = fields.Date(string="Hasta", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Cuenta analítica", readonly=True
    )
    operation_type = fields.Selection(
        selection=[("expense", "Gasto"), ("income", "Ingreso")],
        string="Operación",
        readonly=True,
        help="Con qué expedientes se compara la línea: los de gasto o los de ingreso. "
        "Sale del tipo del presupuesto; en un presupuesto «Ambos», del signo del "
        "importe de la línea (negativo = gasto).",
    )
    amount_budget = fields.Monetary(string="Presupuesto", currency_field="currency_id", readonly=True)
    amount_committed = fields.Monetary(
        string="Comprometido",
        currency_field="currency_id",
        readonly=True,
        help="Órdenes de compra confirmadas y todavía no facturadas de los expedientes "
        "de la cuenta (o el importe definitivo del expediente en etapas sin cotización).",
    )
    amount_real = fields.Monetary(
        string="Real",
        currency_field="currency_id",
        readonly=True,
        help="Facturas publicadas de los expedientes de la cuenta.",
    )
    amount_balance = fields.Monetary(
        string="Disponible",
        currency_field="currency_id",
        readonly=True,
        help="Presupuesto − Comprometido − Real.",
    )
    percent_executed = fields.Float(
        string="% ejecutado",
        readonly=True,
        aggregator="avg",
        help="(Comprometido + Real) sobre el presupuesto.",
    )
    expedient_count = fields.Integer(string="Expedientes", readonly=True)

    # ------------------------------------------------------------------
    # Vista SQL
    # ------------------------------------------------------------------

    @api.model
    def _plan_column_candidates(self, plan):
        """Nombres posibles de la columna de `budget.line` para un plan.

        Cada plan analítico agrega su propia columna a la línea de presupuesto
        (`x_plan<N>_id`; `account_id` para el plan de proyectos). Odoo expone
        `_column_name()` para resolverlo; se prueban además las formas
        conocidas por si la versión instalada no lo tiene. Los sub-planes
        comparten la columna de su plan raíz.
        """
        names = []
        if hasattr(plan, "_column_name"):
            names.append(plan._column_name())
        root = plan.root_id if "root_id" in plan._fields and plan.root_id else plan
        names += [f"x_plan{root.id}_id", f"x_plan{plan.id}_id"]
        return list(dict.fromkeys(names))

    @api.model
    def _is_budget_line_analytic_column(self, name):
        field = self.env["budget.line"]._fields.get(name)
        return bool(
            field
            and field.type == "many2one"
            and field.comodel_name == "account.analytic.account"
            and field.store
            and _column_exists(self.env.cr, "budget_line", name)
        )

    @api.model
    def _budget_line_analytic_columns(self):
        """Columnas de `budget.line` por las que se compara.

        Manda el plan analítico configurado para Expedientes (Configuración de
        expedientes › «Plan analítico», por compañía): es el plan del que
        salen las cuentas analíticas del expediente y sus líneas, así que es
        contra ese plan que tiene sentido comparar. Sin configuración, se
        toman todas las columnas analíticas de la línea de presupuesto, con
        las partidas antes que los proyectos.
        """
        Config = self.env["fund.expedient.config"].sudo()
        configured = []
        for company in self.env["res.company"].sudo().search([]):
            plan = Config.get_analytic_plan(company)
            if not plan:
                continue
            for name in self._plan_column_candidates(plan):
                if self._is_budget_line_analytic_column(name):
                    if name not in configured:
                        configured.append(name)
                    break
        if configured:
            return configured
        columns = [
            name
            for name in self.env["budget.line"]._fields
            if self._is_budget_line_analytic_column(name)
        ]
        return sorted(columns, key=lambda name: (name == "account_id", name))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        columns = self._budget_line_analytic_columns()
        if not columns:
            # Sin planes analíticos en las líneas de presupuesto no hay nada
            # que comparar: vista vacía con la misma forma, para no romper.
            self.env.cr.execute(
                f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT
                        NULL::integer AS id, NULL::integer AS budget_analytic_id,
                        NULL::varchar AS budget_state, NULL::varchar AS budget_type,
                        NULL::date AS date_from, NULL::date AS date_to,
                        NULL::integer AS company_id, NULL::integer AS currency_id,
                        NULL::integer AS analytic_account_id, NULL::varchar AS operation_type,
                        0.0 AS amount_budget, 0.0 AS amount_committed, 0.0 AS amount_real,
                        0.0 AS amount_balance, 0.0 AS percent_executed, 0 AS expedient_count
                    WHERE FALSE
                )
                """
            )
            return
        analytic_expr = "COALESCE(%s)" % ", ".join(f"bl.{c}" for c in columns)
        excluded = ", ".join("'%s'" % s for s in EXCLUDED_BUDGET_STATES)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH lines AS (
                    SELECT
                        bl.id AS line_id,
                        ba.id AS budget_analytic_id,
                        ba.state AS budget_state,
                        ba.budget_type,
                        ba.date_from,
                        ba.date_to,
                        ba.company_id,
                        {analytic_expr} AS analytic_account_id,
                        bl.budget_amount,
                        -- Gasto o ingreso según el tipo del presupuesto. En «Ambos»
                        -- decide el signo de la línea: negativo = gasto.
                        CASE
                            WHEN ba.budget_type = 'revenue' THEN 'income'
                            WHEN ba.budget_type = 'expense' THEN 'expense'
                            WHEN COALESCE(bl.budget_amount, 0.0) < 0 THEN 'expense'
                            ELSE 'income'
                        END AS operation_type
                    FROM budget_line bl
                    JOIN budget_analytic ba ON ba.id = bl.budget_analytic_id
                    WHERE COALESCE(ba.state, '') NOT IN ({excluded})
                      AND {analytic_expr} IS NOT NULL
                ),
                execution AS (
                    SELECT
                        l.line_id,
                        SUM(e.amount_committed) AS amount_committed,
                        SUM(e.amount_real) AS amount_real,
                        COUNT(e.id) AS expedient_count
                    FROM lines l
                    JOIN fund_expedient e
                        ON e.analytic_account_id = l.analytic_account_id
                       AND e.operation_type = l.operation_type
                       AND e.request_date BETWEEN l.date_from AND l.date_to
                       AND (l.company_id IS NULL OR e.company_id = l.company_id)
                       AND COALESCE(e.state, '') <> 'cancel'
                    GROUP BY l.line_id
                )
                SELECT
                    l.line_id AS id,
                    l.budget_analytic_id,
                    l.budget_state,
                    l.budget_type,
                    l.date_from,
                    l.date_to,
                    l.company_id,
                    rc.currency_id,
                    l.analytic_account_id,
                    l.operation_type,
                    ABS(COALESCE(l.budget_amount, 0.0)) AS amount_budget,
                    COALESCE(x.amount_committed, 0.0) AS amount_committed,
                    COALESCE(x.amount_real, 0.0) AS amount_real,
                    ABS(COALESCE(l.budget_amount, 0.0))
                        - COALESCE(x.amount_committed, 0.0)
                        - COALESCE(x.amount_real, 0.0) AS amount_balance,
                    CASE
                        WHEN COALESCE(l.budget_amount, 0.0) <> 0
                        THEN 100.0 * (COALESCE(x.amount_committed, 0.0) + COALESCE(x.amount_real, 0.0))
                             / ABS(l.budget_amount)
                        ELSE 0.0
                    END AS percent_executed,
                    COALESCE(x.expedient_count, 0) AS expedient_count
                FROM lines l
                LEFT JOIN execution x ON x.line_id = l.line_id
                LEFT JOIN res_company rc
                    ON rc.id = COALESCE(l.company_id, (SELECT MIN(id) FROM res_company))
            )
            """
        )

    # ------------------------------------------------------------------
    # Drill-down
    # ------------------------------------------------------------------

    def action_open_expedients(self):
        """Expedientes que forman el comprometido y el real de esta fila."""
        self.ensure_one()
        domain = [
            ("analytic_account_id", "=", self.analytic_account_id.id),
            ("operation_type", "=", self.operation_type),
            ("request_date", ">=", self.date_from),
            ("request_date", "<=", self.date_to),
            ("state", "!=", "cancel"),
        ]
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return {
            "type": "ir.actions.act_window",
            "name": _("Expedientes · %s") % (self.analytic_account_id.display_name or ""),
            "res_model": "fund.expedient",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_group_stage": 1},
        }
