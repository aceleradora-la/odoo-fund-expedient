from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FundBudget(models.Model):
    _name = "fund.budget"
    _description = "Presupuesto"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fiscalyear desc, id desc"

    name = fields.Char(
        string="Nombre",
        required=True,
        tracking=True,
    )
    fiscalyear = fields.Char(
        string="Año",
        required=True,
        default=lambda self: fields.Date.today().strftime("%Y"),
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    date_from = fields.Date(
        string="Desde",
        compute="_compute_dates",
        store=True,
    )
    date_to = fields.Date(
        string="Hasta",
        compute="_compute_dates",
        store=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("open", "Abierto"),
            ("closed", "Cerrado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "fund.budget.line",
        "budget_id",
        string="Líneas",
        copy=True,
    )
    adjustment_ids = fields.One2many(
        "fund.budget.adjustment",
        "budget_id",
        string="Ajustes",
        copy=False,
    )
    total_budget = fields.Monetary(
        string="Presupuesto",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_committed = fields.Monetary(
        string="Comprometido",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_real = fields.Monetary(
        string="Real",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_balance = fields.Monetary(
        string="Saldo",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )

    _sql_constraints = [
        (
            "budget_company_fiscalyear_unique",
            "unique(company_id, fiscalyear)",
            "Ya existe un presupuesto para esa compañía y año.",
        ),
    ]

    @api.constrains("fiscalyear")
    def _check_fiscalyear(self):
        for rec in self:
            if not rec.fiscalyear.isdigit() or not (1900 <= int(rec.fiscalyear) <= 2099):
                raise ValidationError(_("El año debe ser un valor numérico entre 1900 y 2099."))

    @api.depends("fiscalyear")
    def _compute_dates(self):
        for rec in self:
            if rec.fiscalyear and rec.fiscalyear.isdigit():
                rec.date_from = fields.Date.from_string(f"{rec.fiscalyear}-01-01")
                rec.date_to = fields.Date.from_string(f"{rec.fiscalyear}-12-31")
            else:
                rec.date_from = False
                rec.date_to = False

    @api.depends(
        "line_ids.amount_total",
        "line_ids.committed_amount",
        "line_ids.real_amount",
        "line_ids.balance_amount",
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_budget = sum(rec.line_ids.mapped("amount_total"))
            rec.total_committed = sum(rec.line_ids.mapped("committed_amount"))
            rec.total_real = sum(rec.line_ids.mapped("real_amount"))
            rec.total_balance = sum(rec.line_ids.mapped("balance_amount"))

    def action_open(self):
        self.write({"state": "open"})
        return True

    def action_close(self):
        self.write({"state": "closed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_to_draft(self):
        self.write({"state": "draft"})
        return True
