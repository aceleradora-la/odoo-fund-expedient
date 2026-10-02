# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools


class FundExpedientContractInvoiceReport(models.Model):
    """Facturas de las contrataciones de Locación (vista SQL).

    Una fila por factura publicada y expediente de Locación finalizado: lo
    real y lo pagado de cada contratación, para analizarlo por mes, proveedor
    o sector y para el tablero de Contrataciones. Complementa a la proyección
    mensual (`fund.expedient.contract.projection`), que muestra lo
    comprometido.

    Mismo criterio que el «Real» del expediente (`_compute_amounts`):
    - Vínculo: directo (`expedient_ids` de la factura) o a través de la orden
      de compra de sus líneas.
    - Tipo de factura según la operación: de proveedor para los expedientes de
      gasto, de cliente para los de ingreso.
    - Importes en moneda de la compañía y en positivo: las notas de crédito
      restan. `account.move` guarda los de proveedor con signo negativo, lo
      que en un gráfico se vería como barras hacia abajo.

    Una factura vinculada a dos expedientes aparece en ambos, igual que en el
    total real de cada expediente.
    """

    _name = "fund.expedient.contract.invoice.report"
    _description = "Facturación de contrataciones (Locación)"
    _auto = False
    _rec_name = "move_id"
    _order = "date desc, move_id desc"

    move_id = fields.Many2one("account.move", string="Factura", readonly=True)
    expedient_id = fields.Many2one("fund.expedient", string="Expediente", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Proveedor", readonly=True)
    date = fields.Date(string="Fecha", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Cuenta analítica", readonly=True
    )
    requestor_department_id = fields.Many2one(
        "hr.department", string="Sector requirente", readonly=True
    )
    requestor_department_manager_id = fields.Many2one(
        "hr.employee", string="Responsable del sector", readonly=True
    )
    contract_kind = fields.Selection(
        [
            ("service_lease", "Locación de Servicios"),
            ("work_lease", "Locación de Obra"),
        ],
        string="Locación",
        readonly=True,
    )
    payment_state = fields.Selection(
        [
            ("not_paid", "No pagada"),
            ("in_payment", "En proceso de pago"),
            ("paid", "Pagada"),
            ("partial", "Pagada parcialmente"),
            ("reversed", "Revertida"),
            ("blocked", "Bloqueada"),
            ("invoicing_legacy", "Facturación (heredada)"),
        ],
        string="Estado de pago",
        readonly=True,
    )
    amount = fields.Monetary(
        string="Real (facturado)",
        currency_field="currency_id",
        readonly=True,
        help="Total de la factura, impuestos incluidos, en moneda de la compañía.",
    )
    amount_paid = fields.Monetary(
        string="Pagado",
        currency_field="currency_id",
        readonly=True,
        help="Parte de la factura ya cancelada con pagos.",
    )
    amount_residual = fields.Monetary(
        string="Pendiente de pago",
        currency_field="currency_id",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH links AS (
                    SELECT rel.expedient_id, rel.move_id
                    FROM fund_expedient_account_move_rel rel
                    UNION
                    SELECT po_rel.expedient_id, aml.move_id
                    FROM account_move_line aml
                    JOIN purchase_order_line pol ON pol.id = aml.purchase_line_id
                    JOIN fund_expedient_purchase_order_rel po_rel
                        ON po_rel.order_id = pol.order_id
                )
                SELECT
                    ((m.id::bigint << 32) + e.id::bigint) AS id,
                    m.id AS move_id,
                    e.id AS expedient_id,
                    m.commercial_partner_id AS partner_id,
                    COALESCE(m.invoice_date, m.date) AS date,
                    m.company_id,
                    rc.currency_id,
                    e.analytic_account_id,
                    e.requestor_department_id,
                    e.requestor_department_manager_id,
                    e.contract_kind,
                    m.payment_state,
                    -- `*_signed` va en negativo en las facturas de proveedor:
                    -- se invierte para gasto y queda igual para ingreso.
                    s.sign * m.amount_total_signed AS amount,
                    s.sign * (m.amount_total_signed - m.amount_residual_signed) AS amount_paid,
                    s.sign * m.amount_residual_signed AS amount_residual
                FROM links l
                JOIN fund_expedient e ON e.id = l.expedient_id
                JOIN account_move m ON m.id = l.move_id
                JOIN res_company rc ON rc.id = m.company_id
                CROSS JOIN LATERAL (
                    SELECT CASE WHEN e.operation_type = 'income' THEN 1 ELSE -1 END AS sign
                ) s
                WHERE m.state = 'posted'
                  AND e.contract_kind IN ('service_lease', 'work_lease')
                  -- Mismo alcance que los otros reportes de contratación: solo
                  -- expedientes cerrados en la etapa final del flujo.
                  AND e.stage_is_final
                  AND (
                        (e.operation_type = 'income'
                            AND m.move_type IN ('out_invoice', 'out_refund'))
                     OR (COALESCE(e.operation_type, 'expense') <> 'income'
                            AND m.move_type IN ('in_invoice', 'in_refund'))
                  )
            )
            """
        )
