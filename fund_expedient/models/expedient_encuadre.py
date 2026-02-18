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
        """Crear vista lista de encuadres vía código (Odoo 18 list vs tree)."""
        module = "fund_expedient"
        if self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_expedient_encuadre_tree")]
        ):
            return
        view = self.env["ir.ui.view"].create({
            "name": "fund.expedient.encuadre.list",
            "model": "fund.expedient.encuadre",
            "type": "list",
            "arch": """<?xml version="1.0"?>
<list string="Encuadres" create="1" delete="1">
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
