# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools


class FundExpedientBudgetExecution(models.Model):
    """Ejecución presupuestaria «a lo largo», para gráficos.

    Los gráficos de Odoo (y los de los tableros) muestran una sola medida.
    Para ver Presupuesto, Comprometido y Real lado a lado por cuenta
    analítica, esta vista repite cada fila de `fund.expedient.budget.report`
    una vez por concepto: el gráfico agrupa por cuenta y por concepto y mide
    `amount`.

    Se apoya en la vista del reporte. Al recrearse esa vista (`DROP ...
    CASCADE`) cae también esta, que se vuelve a crear a continuación porque
    el modelo se inicializa después (orden de importación en `models`).
    """

    _name = "fund.expedient.budget.execution"
    _description = "Ejecución presupuestaria por concepto (gráficos)"
    _auto = False
    _order = "analytic_account_id, concept"

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
    )
    concept = fields.Selection(
        selection=[
            ("budget", "Presupuesto"),
            ("committed", "Comprometido"),
            ("real", "Real"),
        ],
        string="Concepto",
        readonly=True,
    )
    amount = fields.Monetary(string="Importe", currency_field="currency_id", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        common = """
            r.budget_analytic_id, r.budget_state, r.date_from, r.date_to,
            r.company_id, r.currency_id, r.analytic_account_id, r.operation_type
        """
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT r.id * 3 - 2 AS id, {common},
                       'budget'::varchar AS concept, r.amount_budget AS amount
                  FROM fund_expedient_budget_report r
                UNION ALL
                SELECT r.id * 3 - 1 AS id, {common},
                       'committed'::varchar AS concept, r.amount_committed AS amount
                  FROM fund_expedient_budget_report r
                UNION ALL
                SELECT r.id * 3 AS id, {common},
                       'real'::varchar AS concept, r.amount_real AS amount
                  FROM fund_expedient_budget_report r
            )
            """
        )
