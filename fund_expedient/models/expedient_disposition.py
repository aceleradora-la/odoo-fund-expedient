# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FundExpedientDisposition(models.Model):
    _name = "fund.expedient.disposition"
    _description = "Disposición del expediente"
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
    sequence = fields.Integer(
        default=10,
        help="Orden/numeración configurable para la disposición dentro de la etapa.",
    )
    name = fields.Char(
        string="Disposición",
        compute="_compute_name",
        store=True,
    )
    notes = fields.Text(string="Observaciones")
    file_data = fields.Binary(
        string="Archivo",
        attachment=True,
    )
    file_name = fields.Char(string="Nombre archivo")

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
            "unique(expedient_id, stage_id, sequence)",
            "Ya existe una disposición con esa secuencia para este expediente y etapa.",
        )
    ]

    @api.constrains("file_data", "expedient_id", "stage_id")
    def _check_file_required_by_stage(self):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            if not rec.expedient_id or not rec.stage_id or not rec.expedient_id.type_id:
                continue
            assign = Assign.search(
                [
                    ("type_id", "=", rec.expedient_id.type_id.id),
                    ("stage_id", "=", rec.stage_id.id),
                ],
                limit=1,
            )
            if assign and assign.disposition_file_required and not rec.file_data:
                raise ValidationError(
                    "Esta etapa requiere que la Disposición tenga un archivo adjunto."
                )

    @api.depends("expedient_id.number", "stage_id.name", "sequence")
    def _compute_name(self):
        for rec in self:
            exp = rec.expedient_id.number or ""
            stg = rec.stage_id.name or ""
            if exp and stg:
                rec.name = f"{exp} / {stg} / {rec.sequence}"
            elif exp:
                rec.name = f"{exp} / {rec.sequence}"
            else:
                rec.name = str(rec.sequence or "")

