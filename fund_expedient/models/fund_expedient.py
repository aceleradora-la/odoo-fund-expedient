# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _description = "Expediente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "number"
    _rec_names_search = ["number", "description"]

    number = fields.Char(
        string="Número",
        copy=False,
        readonly=True,
        index=True,
    )
    request_date = fields.Date(
        string="Fecha de solicitud",
        default=fields.Date.context_today,
        tracking=True,
    )
    estimated_need_date = fields.Date(
        string="Fecha estimada de la necesidad",
        tracking=True,
    )
    recommended_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor recomendado",
        tracking=True,
        domain=[("is_company", "=", True)],
    )
    requestor_id = fields.Many2one(
        "hr.employee",
        string="Solicitante",
        tracking=True,
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria asignada",
        tracking=True,
        domain="[('budget_assignment_allowed', '=', True)]",
    )
    encuadre_id = fields.Many2one(
        "fund.expedient.encuadre",
        string="Encuadre",
        tracking=True,
    )
    description = fields.Text(
        string="Descripción de la solicitud",
        tracking=True,
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        group_expand="_read_group_stage_ids",
        tracking=True,
        copy=False,
        ondelete="restrict",
        domain="[('company_id', 'in', [False, company_id])]",
        default=lambda self: self._default_stage_id(),
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("in_progress", "En progreso"),
            ("to_approve", "Por aprobar"),
            ("approved", "Aprobado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        compute="_compute_state",
        store=True,
        tracking=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    # Relación con otros expedientes
    parent_id = fields.Many2one(
        "fund.expedient",
        string="Expediente padre",
        ondelete="set null",
        index=True,
    )
    child_ids = fields.One2many(
        "fund.expedient",
        "parent_id",
        string="Expedientes relacionados",
    )
    # Relaciones con Purchase y Project (many2many: un expediente puede tener muchas)
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "fund_expedient_purchase_order_rel",
        "expedient_id",
        "order_id",
        string="Solicitudes de cotización",
        copy=False,
    )
    purchase_order_count = fields.Integer(
        compute="_compute_purchase_order_count",
        string="Nº Solicitudes",
    )
    project_ids = fields.Many2many(
        "project.project",
        "fund_expedient_project_rel",
        "expedient_id",
        "project_id",
        string="Proyectos",
        copy=False,
    )
    project_count = fields.Integer(
        compute="_compute_project_count",
        string="Nº Proyectos",
    )
    payment_ids = fields.Many2many(
        "account.payment",
        compute="_compute_payment_ids",
        string="Pagos",
        copy=False,
        help="Pagos relacionados: por vinculación directa, por factura directa "
        "o por factura de orden de compra.",
    )
    payment_count = fields.Integer(
        compute="_compute_payment_ids",
        string="Nº Pagos",
    )
    direct_invoice_ids = fields.Many2many(
        "account.move",
        "fund_expedient_account_move_rel",
        "expedient_id",
        "move_id",
        string="Facturas directas",
        copy=False,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund'))]",
        help="Facturas de proveedor sin orden de compra. "
        "Las facturas desde OC se vinculan automáticamente.",
    )
    invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_invoice_ids",
        string="Facturas",
        copy=False,
        help="Facturas de proveedor: desde órdenes de compra o directas.",
    )
    invoice_count = fields.Integer(
        compute="_compute_invoice_ids",
        string="Nº Facturas",
    )

    # Totales (moneda compañía y UF)
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moneda",
    )
    amount_estimated = fields.Monetary(
        string="Total Estimado",
        currency_field="currency_id",
        tracking=True,
    )
    amount_estimated_uf = fields.Float(
        string="Total Estimado (UF)",
        compute="_compute_amount_estimated_uf",
        store=True,
        digits=(16, 4),
    )
    amount_committed = fields.Monetary(
        string="Total Comprometido",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_committed_uf = fields.Float(
        string="Total Comprometido (UF)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
    )
    amount_real = fields.Monetary(
        string="Total Real",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_real_uf = fields.Float(
        string="Total Real (UF)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
    )

    @api.model
    def _default_stage_id(self):
        stage = self.env["fund.expedient.stage"].search(
            [("state_type", "=", "draft")],
            order="sequence",
            limit=1,
        )
        return stage.id if stage else False

    @api.depends("stage_id", "stage_id.state_type")
    def _compute_state(self):
        for rec in self:
            if rec.stage_id:
                rec.state = rec.stage_id.state_type or "draft"
            else:
                rec.state = "draft"

    def _read_group_stage_ids(self, stages, domain):
        return stages.search(domain or [], order="sequence")

    @api.depends("purchase_order_ids")
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    @api.depends("project_ids")
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def _compute_payment_ids(self):
        for rec in self:
            # 1. Pagos con vinculación directa
            payments_direct = self.env["account.payment"].search(
                [("expedient_ids", "in", rec.ids)]
            )
            # 2. Facturas del expediente (OC + directas)
            all_invoices = rec.purchase_order_ids.mapped("invoice_ids") | rec.direct_invoice_ids
            # 3. Pagos reconciliados con esas facturas
            payments_via_invoice = all_invoices.mapped("reconciled_payment_ids")
            all_payments = payments_direct | payments_via_invoice
            rec.payment_ids = all_payments
            rec.payment_count = len(all_payments)

    @api.depends("purchase_order_ids", "purchase_order_ids.invoice_ids", "direct_invoice_ids")
    def _compute_invoice_ids(self):
        for rec in self:
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids")
            all_invoices = invoices_po | rec.direct_invoice_ids
            rec.invoice_ids = all_invoices
            rec.invoice_count = len(all_invoices)

    @api.depends("amount_estimated", "request_date", "company_id")
    def _compute_amount_estimated_uf(self):
        UfRate = self.env["fund.uf.rate"]
        for rec in self:
            if not rec.amount_estimated or not rec.request_date:
                rec.amount_estimated_uf = 0.0
                continue
            rate = UfRate.get_rate(rec.company_id, rec.request_date)
            rec.amount_estimated_uf = rate and (rec.amount_estimated / rate) or 0.0

    @api.depends(
        "purchase_order_ids",
        "purchase_order_ids.state",
        "purchase_order_ids.invoice_status",
        "purchase_order_ids.amount_total",
        "purchase_order_ids.amount_total_cc",
        "purchase_order_ids.date_order",
        "purchase_order_ids.currency_id",
        "purchase_order_ids.invoice_ids",
        "purchase_order_ids.invoice_ids.state",
        "purchase_order_ids.invoice_ids.amount_total_signed",
        "direct_invoice_ids",
        "direct_invoice_ids.state",
        "direct_invoice_ids.amount_total_signed",
        "company_id",
    )
    def _compute_amounts(self):
        UfRate = self.env["fund.uf.rate"]
        for rec in self:
            company_currency = rec.company_id.currency_id

            # Total Comprometido: OC confirmadas sin factura (o no totalmente facturadas)
            pos_committed = rec.purchase_order_ids.filtered(
                lambda po: po.state in ("purchase", "done")
                and po.invoice_status != "invoiced"
            )
            amount_committed = sum(
                po.currency_id.with_context(date=po.date_order).compute(
                    po.amount_total, company_currency
                )
                for po in pos_committed
            )
            rec.amount_committed = amount_committed

            # Total Comprometido en UF
            committed_uf = 0.0
            for po in pos_committed:
                rate = UfRate.get_rate(rec.company_id, po.date_order.date())
                if rate:
                    amt_cc = po.currency_id.with_context(
                        date=po.date_order
                    ).compute(po.amount_total, company_currency)
                    committed_uf += amt_cc / rate
            rec.amount_committed_uf = committed_uf

            # Total Real: facturas posteadas (desde OC o directas)
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids").filtered(
                lambda m: m.state == "posted"
            )
            invoices_direct = rec.direct_invoice_ids.filtered(
                lambda m: m.state == "posted"
            )
            all_invoices = invoices_po | invoices_direct
            amount_real = 0.0
            amount_real_uf = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                # amount_total_signed: negativo para facturas, positivo para devoluciones
                signed = -inv.amount_total_signed
                amt_cc = inv.currency_id.with_context(date=inv_date).compute(
                    signed, company_currency
                )
                amount_real += amt_cc
                rate = UfRate.get_rate(rec.company_id, inv_date)
                if rate:
                    amount_real_uf += amt_cc / rate
            rec.amount_real = amount_real
            rec.amount_real_uf = amount_real_uf

    @api.model
    def create(self, vals):
        if vals.get("number", "/") == "/":
            seq = self.env["ir.sequence"].next_by_code("fund.expedient") or "/"
            vals["number"] = seq
        return super().create(vals)

    def unlink(self):
        raise UserError(
            "No se pueden eliminar expedientes para mantener la secuencia sin huecos. "
            "Use la opción 'Cancelar' para anular un expediente."
        )

    def action_cancel(self):
        """Mover expediente a estado Cancelado."""
        cancel_stage = self.env["fund.expedient.stage"].search(
            [("state_type", "=", "cancel")], limit=1
        )
        if not cancel_stage:
            raise UserError("No existe una etapa de tipo 'Cancelado' configurada.")
        return self.write({"stage_id": cancel_stage.id})

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de cotización",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.purchase_order_ids.ids)],
            "context": {"default_expedient_ids": [(4, self.id)]},
        }

    def action_view_projects(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Proyectos",
            "res_model": "project.project",
            "view_mode": "list,form",
            "domain": [("id", "in", self.project_ids.ids)],
            "context": {"default_expedient_ids": [(4, self.id)]},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Facturas",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {
                "default_expedient_ids": [(4, self.id)],
                "default_move_type": "in_invoice",
            },
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Pagos",
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payment_ids.ids)],
            "context": {
                "default_expedient_ids": [(4, self.id)],
                "default_partner_type": "supplier",
            },
        }
