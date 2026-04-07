from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FundBudgetAdjustment(models.Model):
    _name = "fund.budget.adjustment"
    _description = "Ajuste presupuestario"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Nombre",
        required=True,
        tracking=True,
    )
    date = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    budget_id = fields.Many2one(
        "fund.budget",
        string="Presupuesto",
        required=True,
        ondelete="cascade",
        tracking=True,
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
    line_ids = fields.One2many(
        "fund.budget.adjustment.line",
        "adjustment_id",
        string="Líneas",
        copy=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("posted", "Publicado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        tracking=True,
    )
    amount_total = fields.Monetary(
        string="Total ajuste",
        compute="_compute_amount_total",
        store=True,
        currency_field="currency_id",
    )

    @api.depends("line_ids.amount")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount"))

    def action_post(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debe ingresar al menos una línea de ajuste."))
            if rec.budget_id.state not in ("draft", "open"):
                raise UserError(
                    _("Solo puede publicar ajustes en presupuestos en borrador o abiertos.")
                )
        self.write({"state": "posted"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_to_draft(self):
        self.write({"state": "draft"})
        return True


class FundBudgetAdjustmentLine(models.Model):
    _name = "fund.budget.adjustment.line"
    _description = "Línea de ajuste presupuestario"

    adjustment_id = fields.Many2one(
        "fund.budget.adjustment",
        string="Ajuste",
        required=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        related="adjustment_id.state",
        string="Estado",
        store=True,
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
    company_id = fields.Many2one(
        related="adjustment_id.company_id",
        string="Compañía",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="adjustment_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    amount = fields.Monetary(
        string="Monto ajuste",
        required=True,
        currency_field="currency_id",
        help="Positivo para ampliar presupuesto, negativo para reducirlo.",
    )
    note = fields.Char(string="Detalle")
