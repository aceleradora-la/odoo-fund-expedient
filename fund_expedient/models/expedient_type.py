# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.sql import table_exists
from odoo.exceptions import ValidationError


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
    use_requestor = fields.Boolean(
        string="Solicitante",
        help="Si está activo, la etapa se asigna al Solicitante del expediente (requestor_id). "
        "En ese caso no se usan grupos, puestos ni usuarios.",
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
    user_ids = fields.Many2many(
        "res.users",
        "fund_expedient_type_stage_assign_user_rel",
        "assign_id",
        "user_id",
        string="Usuarios",
        help="Usuarios concretos asignados a esta etapa (además de grupos y puestos).",
    )
    hide_type_id = fields.Boolean(string="Ocultar Tipo")
    hide_encuadre_id = fields.Boolean(string="Ocultar Encuadre")
    hide_estimated_need_date = fields.Boolean(string="Ocultar Fecha estimada")
    hide_recommended_supplier_id = fields.Boolean(string="Ocultar Proveedor recomendado")
    hide_budget_position_id = fields.Boolean(string="Ocultar Partida presupuestaria")
    hide_amount_estimated = fields.Boolean(string="Ocultar Total estimado")
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

    @api.onchange("use_requestor")
    def _onchange_use_requestor(self):
        if self.use_requestor:
            self.group_ids = [(5, 0, 0)]
            self.job_ids = [(5, 0, 0)]
            self.user_ids = [(5, 0, 0)]

    @api.constrains("use_requestor", "group_ids", "job_ids", "user_ids")
    def _check_requestor_exclusive(self):
        for rec in self:
            if rec.use_requestor and (rec.group_ids or rec.job_ids or rec.user_ids):
                raise ValidationError(
                    "Si marca 'Solicitante', no puede configurar grupos, puestos o usuarios en esa etapa."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("use_requestor"):
                vals["group_ids"] = [(5, 0, 0)]
                vals["job_ids"] = [(5, 0, 0)]
                vals["user_ids"] = [(5, 0, 0)]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("use_requestor"):
            vals = dict(vals)
            vals["group_ids"] = [(5, 0, 0)]
            vals["job_ids"] = [(5, 0, 0)]
            vals["user_ids"] = [(5, 0, 0)]
        return super().write(vals)

    def init(self):
        """Eliminar constraints legacy que impidan reutilizar etapas entre tipos.

        En versiones anteriores pudo existir un UNIQUE(stage_id) en la tabla, lo que
        bloquea usar la misma etapa en tipos distintos. Este modelo ya define el
        constraint correcto: UNIQUE(type_id, stage_id).
        """
        # En upgrades, este init puede correrse antes de que la tabla exista.
        if not table_exists(self.env.cr, "fund_expedient_type_stage_assign"):
            return
        self.env.cr.execute(
            """
            DO $$
            DECLARE
                r record;
            BEGIN
                FOR r IN (
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE con.contype = 'u'
                      AND nsp.nspname = current_schema()
                      AND rel.relname = 'fund_expedient_type_stage_assign'
                      AND (
                        SELECT array_agg(att.attname ORDER BY att.attname)
                        FROM unnest(con.conkey) AS k(attnum)
                        JOIN pg_attribute att
                          ON att.attrelid = rel.oid
                         AND att.attnum = k.attnum
                      ) = ARRAY['stage_id']
                ) LOOP
                    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', 'fund_expedient_type_stage_assign', r.conname);
                END LOOP;
            END $$;
            """
        )


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
    encuadre_ids = fields.Many2many(
        "fund.expedient.encuadre",
        "fund_expedient_type_encuadre_rel",
        "type_id",
        "encuadre_id",
        string="Encuadres permitidos",
        help="Lista de encuadres que pueden seleccionarse para este tipo de expediente.",
    )
    unit_mode = fields.Selection(
        [
            ("ur", "Unidad Retributiva (UR)"),
            ("uf", "Unidad Funcional (UF)"),
        ],
        string="Unidad de aprobación",
        default="ur",
        required=True,
        help="Unidad utilizada para los umbrales de aprobación y análisis (UR o UF).",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )
