# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
