# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ExpedientTypeStageAssign(models.Model):
    _name = "fund.expedient.type.stage.assign"
    _description = "Asignación por Tipo y Etapa"
    _order = "type_id, stage_id"
    _rec_name = "display_name"

    type_id = fields.Many2one(
        "fund.expedient.type",
        string="Tipo",
        required=True,
        ondelete="cascade",
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        required=True,
        ondelete="cascade",
    )
    group_ids = fields.Many2many(
        "res.groups",
        "fund_expedient_type_stage_assign_group_rel",
        "assign_id",
        "group_id",
        string="Grupos de usuarios",
        help="Usuarios de estos grupos pueden ser asignados o son responsables en esta etapa.",
    )
    job_ids = fields.Many2many(
        "hr.job",
        "fund_expedient_type_stage_assign_job_rel",
        "assign_id",
        "job_id",
        string="Puestos del organigrama",
        help="Empleados con estos puestos pueden ser asignados o son responsables en esta etapa.",
    )
    company_id = fields.Many2one(
        related="type_id.company_id",
        store=True,
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "type_stage_uniq",
            "unique(type_id, stage_id)",
            "Ya existe una asignación para este tipo y etapa.",
        )
    ]

    @api.depends("type_id", "stage_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.type_id and rec.stage_id:
                rec.display_name = f"{rec.type_id.name} / {rec.stage_id.name}"
            else:
                rec.display_name = ""


class ExpedientType(models.Model):
    _name = "fund.expedient.type"
    _description = "Tipo de Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, string="Tipo")
    sequence = fields.Integer(default=10)
    stage_assign_ids = fields.One2many(
        "fund.expedient.type.stage.assign",
        "type_id",
        string="Asignaciones por etapa",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )
