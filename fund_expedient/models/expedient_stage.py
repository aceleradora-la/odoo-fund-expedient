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
            ("purchases", "Compras"),
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
    spend_request_mode = fields.Selection(
        selection=[
            ("none", "Sin Solicitud de Gasto"),
            ("preventiva", "Permite SG preventiva"),
            ("final", "Permite SG definitiva"),
        ],
        string="Solicitud de Gasto",
        default="none",
        required=True,
        help="Habilita la creación de Solicitud de Gasto (preventiva o definitiva) desde el expediente en esta etapa.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    @api.model
    def init_expedient_stage_view(self):
        """Crear vistas de etapas vía código (Odoo 18 list vs tree)."""
        module = "fund_expedient"
        View = self.env["ir.ui.view"]
        IrModelData = self.env["ir.model.data"]

        list_arch = """<?xml version="1.0"?>
<list string="Etapas de expediente" create="1" delete="1" edit="1">
    <field name="sequence" widget="handle"/>
    <field name="name"/>
    <field name="state_type"/>
    <field name="spend_request_mode" optional="hide"/>
    <field name="fold"/>
    <field name="report_id" optional="show"/>
</list>"""

        form_arch = """<?xml version="1.0"?>
<form string="Etapa de expediente">
    <sheet>
        <group>
            <group>
                <field name="name"/>
                <field name="sequence"/>
                <field name="state_type"/>
                <field name="fold"/>
            </group>
            <group>
                <field name="report_id"/>
                <field name="spend_request_mode"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </group>
        </group>
    </sheet>
</form>"""
        # Vista lista
        md_list = IrModelData.search(
            [("module", "=", module), ("name", "=", "view_expedient_stage_tree")], limit=1
        )
        if not md_list:
            view = View.create(
                {
                    "name": "fund.expedient.stage.list",
                    "model": "fund.expedient.stage",
                    "type": "list",
                    "arch": list_arch,
                }
            )
            IrModelData.create(
                {
                    "name": "view_expedient_stage_tree",
                    "module": module,
                    "model": "ir.ui.view",
                    "res_id": view.id,
                    "noupdate": True,
                }
            )
        else:
            view = View.browse(md_list.res_id)
            # Si el campo nuevo no está en la vista, actualizar el arch (sin depender de upgrades manuales).
            if view and "spend_request_mode" not in (view.arch_db or ""):
                view.write({"arch": list_arch})
        # Vista formulario para editar etapas
        md_form = IrModelData.search(
            [("module", "=", module), ("name", "=", "view_expedient_stage_form")], limit=1
        )
        if not md_form:
            form_view = View.create(
                {
                    "name": "fund.expedient.stage.form",
                    "model": "fund.expedient.stage",
                    "type": "form",
                    "arch": form_arch,
                }
            )
            IrModelData.create(
                {
                    "name": "view_expedient_stage_form",
                    "module": module,
                    "model": "ir.ui.view",
                    "res_id": form_view.id,
                    "noupdate": True,
                }
            )
        else:
            form_view = View.browse(md_form.res_id)
            if form_view and "spend_request_mode" not in (form_view.arch_db or ""):
                form_view.write({"arch": form_arch})
