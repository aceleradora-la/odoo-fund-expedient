# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundExpedientResolution(models.Model):
    _name = "fund.expedient.resolution"
    _description = "Resolución del expediente"
    _order = "sequence, id"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        required=True,
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.context.get("default_stage_id"),
    )
    sequence = fields.Integer(default=10, help="Orden visual en listas.")
    number = fields.Char(
        string="Número",
        readonly=True,
        index=True,
        copy=False,
        default="/",
        help="Numeración automática según Secuencias de Odoo (por compañía).",
    )
    name = fields.Char(
        string="Resolución",
        compute="_compute_name",
        store=True,
    )
    notes = fields.Html(string="Observaciones")

    document_ids = fields.One2many(
        "fund.expedient.document",
        "resolution_id",
        string="Documentos relacionados",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "expedient_stage_number_uniq",
            "unique(expedient_id, stage_id, number)",
            "Ya existe una resolución con ese número para este expediente y etapa.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for vals in vals_list:
            exp_id = vals.get("expedient_id") or self.env.context.get("default_expedient_id")
            stage_id = vals.get("stage_id") or self.env.context.get("default_stage_id")
            if exp_id and not vals.get("expedient_id"):
                vals["expedient_id"] = exp_id
            if stage_id and not vals.get("stage_id"):
                vals["stage_id"] = stage_id

            # Observaciones por defecto desde config tipo×etapa (si está vacía).
            if (not vals.get("notes") or not str(vals.get("notes")).strip()) and exp_id and stage_id:
                exp = self.env["fund.expedient"].browse(exp_id)
                if exp.type_id:
                    assign = Assign.search(
                        [("type_id", "=", exp.type_id.id), ("stage_id", "=", stage_id)],
                        limit=1,
                    )
                    if assign and assign.default_resolution_notes:
                        vals["notes"] = assign.default_resolution_notes

            # Numeración automática por compañía (configurable en Secuencias).
            if vals.get("number", "/") == "/":
                company = False
                if exp_id:
                    company = self.env["fund.expedient"].browse(exp_id).company_id
                seq_env = (
                    self.env["ir.sequence"].with_company(company)
                    if company
                    else self.env["ir.sequence"]
                )
                vals["number"] = seq_env.next_by_code("fund.expedient.resolution") or "/"

        return super().create(vals_list)

    @api.depends("number", "stage_id.name")
    def _compute_name(self):
        for rec in self:
            stg = rec.stage_id.name or ""
            rec.name = f"{rec.number} ({stg})" if stg and rec.number else (rec.number or "")

