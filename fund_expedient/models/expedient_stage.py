# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ExpedientStage(models.Model):
    _name = "fund.expedient.stage"
    _description = "Etapa de Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    state_type = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("in_progress", "En progreso"),
            ("to_approve", "Por aprobar"),
            ("approved", "Aprobado"),
            ("cancel", "Cancelado"),
        ],
        string="Tipo de estado",
        default="draft",
        required=True,
        help="Determina el estado del expediente cuando está en esta etapa (para validación por niveles).",
    )
    fold = fields.Boolean(
        default=False,
        help="Etapas plegadas en la vista Kanban.",
    )
    report_id = fields.Many2one(
        "ir.actions.report",
        string="Reporte asociado",
        domain=[("model_id.model", "=", "fund.expedient")],
        help="Si se define, se mostrará el botón Imprimir con este reporte en el expediente.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    @api.model
    def init_expedient_stage_view(self):
        """Crear vista lista de etapas vía código (Odoo 18 list vs tree)."""
        module = "fund_expedient"
        if self.env["ir.model.data"].search(
            [("module", "=", module), ("name", "=", "view_expedient_stage_tree")]
        ):
            return
        view = self.env["ir.ui.view"].create({
            "name": "fund.expedient.stage.list",
            "model": "fund.expedient.stage",
            "type": "list",
            "arch": """<?xml version="1.0"?>
<list string="Etapas de expediente" create="1" delete="1">
    <field name="sequence" widget="handle"/>
    <field name="name"/>
    <field name="state_type"/>
    <field name="fold"/>
    <field name="report_id" optional="show"/>
</list>""",
        })
        self.env["ir.model.data"].create({
            "name": "view_expedient_stage_tree",
            "module": module,
            "model": "ir.ui.view",
            "res_id": view.id,
            "noupdate": True,
        })
