# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools


class FundExpedientContractProjection(models.Model):
    """Proyección mensual de flujo de caja para expedientes de locación.

    Vista SQL (sin tabla propia) que expande cada línea de expediente de
    locación (servicios u obra) con Fecha Inicio/Fin en una fila por mes del
    rango contratado, repartiendo el importe total en partes iguales entre la
    cantidad de meses. Pensada para analizarse en vista pivote (filas =
    expediente/proveedor/cuenta analítica; columnas = mes; medida = importe).
    """

    _name = "fund.expedient.contract.projection"
    _description = "Proyección mensual de contrataciones (Locación)"
    _auto = False
    _rec_name = "expedient_id"
    _order = "expedient_id, month, line_id"

    line_id = fields.Many2one("fund.expedient.line", string="Línea", readonly=True)
    expedient_id = fields.Many2one("fund.expedient", string="Expediente", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Cuenta analítica", readonly=True
    )
    partner_id = fields.Many2one("res.partner", string="Proveedor contratado", readonly=True)
    contract_kind = fields.Selection(
        [
            ("service_lease", "Locación de Servicios"),
            ("work_lease", "Locación de Obra"),
        ],
        string="Locación",
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Producto/Servicio", readonly=True)
    date_start = fields.Date(string="Fecha inicio", readonly=True)
    date_end = fields.Date(string="Fecha fin", readonly=True)
    month = fields.Date(string="Mes", readonly=True, help="Primer día del mes proyectado.")
    month_count = fields.Integer(string="Meses contratados", readonly=True)
    amount_total = fields.Monetary(
        string="Importe total línea", currency_field="currency_id", readonly=True
    )
    amount_month = fields.Monetary(
        string="Importe del mes", currency_field="currency_id", readonly=True,
        help="Importe total de la línea dividido la cantidad de meses contratados.",
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH base AS (
                    SELECT
                        l.id AS line_id,
                        l.expedient_id,
                        e.company_id,
                        l.analytic_account_id,
                        l.product_id,
                        e.contract_kind,
                        l.date_start,
                        l.date_end,
                        (
                            (EXTRACT(YEAR FROM l.date_end)::int * 12 + EXTRACT(MONTH FROM l.date_end)::int)
                            - (EXTRACT(YEAR FROM l.date_start)::int * 12 + EXTRACT(MONTH FROM l.date_start)::int)
                            + 1
                        ) AS month_count,
                        COALESCE(NULLIF(l.amount_final_line, 0.0), l.amount_estimated_line) AS amount_total
                    FROM fund_expedient_line l
                    JOIN fund_expedient e ON e.id = l.expedient_id
                    WHERE e.contract_kind IN ('service_lease', 'work_lease')
                      AND l.display_type IS NULL
                      AND l.date_start IS NOT NULL
                      AND l.date_end IS NOT NULL
                      AND l.date_end >= l.date_start
                )
                SELECT
                    ((b.line_id::bigint << 12) + gs.n::bigint) AS id,
                    b.line_id,
                    b.expedient_id,
                    b.company_id,
                    rc.currency_id,
                    b.analytic_account_id,
                    b.product_id,
                    b.contract_kind,
                    b.date_start,
                    b.date_end,
                    b.month_count,
                    b.amount_total,
                    (date_trunc('month', b.date_start) + (gs.n || ' month')::interval)::date AS month,
                    CASE WHEN b.month_count > 0 THEN b.amount_total / b.month_count ELSE b.amount_total END AS amount_month,
                    po.partner_id
                FROM base b
                JOIN res_company rc ON rc.id = b.company_id
                JOIN LATERAL generate_series(0, b.month_count - 1) AS gs(n) ON TRUE
                LEFT JOIN LATERAL (
                    SELECT rel.order_id
                    FROM fund_expedient_purchase_order_rel rel
                    WHERE rel.expedient_id = b.expedient_id
                    ORDER BY rel.order_id
                    LIMIT 1
                ) first_po ON TRUE
                LEFT JOIN purchase_order po ON po.id = first_po.order_id
            )
            """
        )
