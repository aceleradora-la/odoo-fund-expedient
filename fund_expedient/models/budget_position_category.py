# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class BudgetPositionCategory(models.Model):
    _name = "fund.budget.position.category"
    _description = "Categoría de Partida Presupuestaria"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    @api.model
    def init_budget_position_views(self):
        """Crear vistas vía código para evitar XML tree/list en Odoo 18 (deployment con código antiguo)."""
        View = self.env["ir.ui.view"]
        module = "fund_expedient"

        # Vista lista categorías
        if not self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_budget_position_category_list")]
        ):
            view_vals = {
                "name": "fund.budget.position.category.list",
                "model": "fund.budget.position.category",
                "type": "list",
                "arch": """<?xml version="1.0"?>
<list string="Categorías de partida">
    <field name="sequence" widget="handle"/>
    <field name="name"/>
</list>""",
            }
            view = View.create(view_vals)
            self.env["ir.model.data"].create(
                {
                    "name": "view_budget_position_category_list",
                    "module": module,
                    "model": "ir.ui.view",
                    "res_id": view.id,
                    "noupdate": True,
                }
            )

        # Vista lista partidas
        if not self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_budget_position_list")]
        ):
            view_vals = {
                "name": "fund.budget.position.list",
                "model": "fund.budget.position",
                "type": "list",
                "arch": """<?xml version="1.0"?>
<list string="Partidas presupuestarias" create="1" delete="1">
    <field name="sequence" widget="handle"/>
    <field name="code"/>
    <field name="name"/>
    <field name="type"/>
    <field name="budget_assignment_allowed"/>
    <field name="category_id"/>
    <field name="parent_id" optional="hide"/>
</list>""",
            }
            view = View.create(view_vals)
            self.env["ir.model.data"].create(
                {
                    "name": "view_budget_position_list",
                    "module": module,
                    "model": "ir.ui.view",
                    "res_id": view.id,
                    "noupdate": True,
                }
            )

        # Vista formulario partidas
        if not self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_budget_position_form")]
        ):
            view_vals = {
                "name": "fund.budget.position.form",
                "model": "fund.budget.position",
                "type": "form",
                "arch": """<?xml version="1.0"?>
<form string="Partida presupuestaria">
    <sheet>
        <group>
            <group>
                <field name="code"/>
                <field name="name"/>
                <field name="type"/>
                <field name="budget_assignment_allowed"/>
                <field name="category_id"/>
                <field name="parent_id"/>
            </group>
        </group>
    </sheet>
</form>""",
            }
            view = View.create(view_vals)
            self.env["ir.model.data"].create(
                {
                    "name": "view_budget_position_form",
                    "module": module,
                    "model": "ir.ui.view",
                    "res_id": view.id,
                    "noupdate": True,
                }
            )
