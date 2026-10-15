# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ExpedientEncuadre(models.Model):
    _name = "fund.expedient.encuadre"
    _description = "Encuadre del Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    @api.model
    def init_expedient_encuadre_view(self):
        """Crear vistas de encuadres vía código (Odoo 18 list vs tree)."""
        module = "fund_expedient"
        View = self.env["ir.ui.view"]
        # Vista lista
        if not self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_expedient_encuadre_tree")]
        ):
            view = View.create({
                "name": "fund.expedient.encuadre.list",
                "model": "fund.expedient.encuadre",
                "type": "list",
                "arch": """<?xml version="1.0"?>
<list string="Encuadres" create="1" delete="1" edit="1">
    <field name="sequence" widget="handle"/>
    <field name="name"/>
</list>""",
            })
            self.env["ir.model.data"].create({
                "name": "view_expedient_encuadre_tree",
                "module": module,
                "model": "ir.ui.view",
                "res_id": view.id,
                "noupdate": True,
            })
        # Vista formulario para editar encuadres
        if not self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_expedient_encuadre_form")]
        ):
            form_view = View.create({
                "name": "fund.expedient.encuadre.form",
                "model": "fund.expedient.encuadre",
                "type": "form",
                "arch": """<?xml version="1.0"?>
<form string="Encuadre">
    <sheet>
        <group>
            <field name="name"/>
            <field name="sequence"/>
            <field name="company_id" groups="base.group_multi_company"/>
        </group>
    </sheet>
</form>""",
            })
            self.env["ir.model.data"].create({
                "name": "view_expedient_encuadre_form",
                "module": module,
                "model": "ir.ui.view",
                "res_id": form_view.id,
                "noupdate": True,
            })
