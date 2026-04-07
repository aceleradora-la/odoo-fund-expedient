from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LegacyBudgetPositionMigrationWizard(models.TransientModel):
    _name = "fund.legacy.budget.position.migration.wizard"
    _description = "Migración legacy: Partidas → Cuentas analíticas"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        "fund.legacy.budget.position.migration.wizard.line",
        "wizard_id",
        string="Mapeos",
        copy=False,
    )
    apply_to_expedients = fields.Boolean(
        string="Actualizar expedientes",
        default=True,
        help="Setea la cuenta analítica en expedientes que tengan partida legacy.",
    )
    apply_to_budget_lines = fields.Boolean(
        string="Actualizar líneas de presupuesto legacy",
        default=True,
        help="Setea la cuenta analítica en líneas de presupuesto (si aún tienen partida legacy).",
    )
    apply_to_adjustment_lines = fields.Boolean(
        string="Actualizar líneas de ajuste legacy",
        default=True,
    )

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Debe ingresar al menos un mapeo."))

        mapping = {
            ln.budget_position_id.id: ln.analytic_account_id.id
            for ln in self.line_ids
            if ln.budget_position_id and ln.analytic_account_id
        }
        if not mapping:
            raise UserError(_("No hay mapeos válidos para aplicar."))

        if self.apply_to_expedients:
            expedients = self.env["fund.expedient"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("budget_position_id", "in", list(mapping.keys())),
                    ("analytic_account_id", "=", False),
                ]
            )
            for exp in expedients:
                exp.analytic_account_id = mapping.get(exp.budget_position_id.id)

        if self.apply_to_budget_lines:
            lines = self.env["fund.budget.line"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("budget_position_id", "in", list(mapping.keys())),
                    ("analytic_account_id", "=", False),
                ]
            )
            for ln in lines:
                ln.analytic_account_id = mapping.get(ln.budget_position_id.id)

        if self.apply_to_adjustment_lines:
            adj_lines = self.env["fund.budget.adjustment.line"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("budget_position_id", "in", list(mapping.keys())),
                    ("analytic_account_id", "=", False),
                ]
            )
            for ln in adj_lines:
                ln.analytic_account_id = mapping.get(ln.budget_position_id.id)

        return {"type": "ir.actions.act_window_close"}


class LegacyBudgetPositionMigrationWizardLine(models.TransientModel):
    _name = "fund.legacy.budget.position.migration.wizard.line"
    _description = "Mapeo Partida → Cuenta analítica"

    wizard_id = fields.Many2one(
        "fund.legacy.budget.position.migration.wizard",
        required=True,
        ondelete="cascade",
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida legacy",
        required=True,
        domain="[('company_id', '=', wizard_id.company_id)]",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        required=True,
        domain="[('company_id', 'in', [False, wizard_id.company_id])]",
    )

