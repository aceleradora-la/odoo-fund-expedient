# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FundExpedientDisposition(models.Model):
    _name = "fund.expedient.disposition"
    _description = "Disposición del expediente"
    _order = "stage_id, sequence_number, id"

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
    sequence_number = fields.Integer(
        string="Nº Disposición",
        default=1,
        help="Numeración configurable de la disposición (usada en el identificador).",
    )
    number = fields.Char(
        string="Número",
        compute="_compute_number",
        store=True,
        index=True,
    )
    name = fields.Char(
        string="Disposición",
        compute="_compute_name",
        store=True,
    )
    notes = fields.Html(string="Observaciones")

    document_ids = fields.One2many(
        "fund.expedient.document",
        "disposition_id",
        string="Documentos relacionados",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "expedient_stage_sequence_uniq",
            "unique(expedient_id, stage_id, sequence_number)",
            "Ya existe una disposición con ese número para este expediente y etapa.",
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
                    if assign and assign.default_disposition_notes:
                        vals["notes"] = assign.default_disposition_notes

        return super().create(vals_list)

    @api.depends("expedient_id.number", "stage_id.name", "sequence_number")
    def _compute_number(self):
        for rec in self:
            exp = (rec.expedient_id.number or "").strip()
            stg = (rec.stage_id.name or "").strip()
            if exp and stg:
                rec.number = f"{exp}-{stg}-{rec.sequence_number}"
            elif exp:
                rec.number = f"{exp}-{rec.sequence_number}"
            else:
                rec.number = str(rec.sequence_number or "")

    @api.depends("number", "stage_id.name")
    def _compute_name(self):
        for rec in self:
            stg = rec.stage_id.name or ""
            rec.name = f"{rec.number} ({stg})" if stg and rec.number else (rec.number or "")

