# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundExpedientDocument(models.Model):
    _name = "fund.expedient.document"
    _description = "Documento del expediente"
    _order = "sequence, id"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    number = fields.Char(
        string="Nº Documento",
        readonly=True,
        index=True,
        copy=False,
        help="Numeración correlativa por expediente: <NºExpediente>-###.",
    )
    sequence_in_expedient = fields.Integer(
        string="Correlativo (expediente)",
        readonly=True,
        copy=False,
        help="Correlativo interno usado para numerar documentos dentro del expediente.",
    )
    name = fields.Char(string="Documento")
    delivered = fields.Boolean(string="Entregado")
    notes = fields.Text(string="Observaciones")
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa origen",
        default=lambda self: self.env.context.get("default_stage_id"),
        required=True,
    )
    disposition_id = fields.Many2one(
        "fund.expedient.disposition",
        string="Disposición",
        ondelete="set null",
        domain="[('expedient_id', '=', expedient_id), ('stage_id', '=', stage_id)]",
        help="Si existe una disposición para la etapa, el documento puede asociarse a ella.",
    )
    file_data = fields.Binary(
        string="Archivo",
        attachment=True,
    )
    file_name = fields.Char(string="Nombre archivo")
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )

    @api.onchange("file_name")
    def _onchange_file_name_set_name(self):
        for rec in self:
            if rec.file_name and (not rec.name or not str(rec.name).strip()):
                rec.name = rec.file_name

    @api.model_create_multi
    def create(self, vals_list):
        # Precalcular correlativos por expediente en caso de multi-create.
        exp_ids = {
            vals.get("expedient_id")
            for vals in vals_list
            if vals.get("expedient_id") and not vals.get("sequence_in_expedient")
        }
        max_by_exp = {}
        for exp_id in sorted(eid for eid in exp_ids if eid):
            # Lock del expediente para evitar duplicados en concurrencia.
            self.env.cr.execute(
                """
                SELECT id
                  FROM fund_expedient
                 WHERE id = %s
                 FOR UPDATE
                """,
                [exp_id],
            )
            self.env.cr.execute(
                """
                SELECT COALESCE(MAX(sequence_in_expedient), 0)
                  FROM fund_expedient_document
                 WHERE expedient_id = %s
                """,
                [exp_id],
            )
            max_by_exp[exp_id] = int(self.env.cr.fetchone()[0] or 0)
        counters = {exp_id: 0 for exp_id in max_by_exp}

        for vals in vals_list:
            # Etapa fija desde el contexto cuando se crea desde el expediente.
            default_stage_id = self.env.context.get("default_stage_id")
            if default_stage_id:
                vals["stage_id"] = default_stage_id

            # Nombre del documento: por defecto igual al nombre del archivo.
            if (not vals.get("name") or not str(vals.get("name")).strip()) and vals.get("file_name"):
                vals["name"] = vals["file_name"]

            # Si existe una única disposición para el expediente+etapa, autovincular.
            if vals.get("expedient_id") and vals.get("stage_id") and not vals.get("disposition_id"):
                disp = self.env["fund.expedient.disposition"].search(
                    [
                        ("expedient_id", "=", vals["expedient_id"]),
                        ("stage_id", "=", vals["stage_id"]),
                    ],
                    order="sequence, id",
                    limit=2,
                )
                if len(disp) == 1:
                    vals["disposition_id"] = disp.id

            # Numeración correlativa por expediente: <NºExpediente>-###.
            if vals.get("expedient_id") and not vals.get("sequence_in_expedient"):
                exp_id = vals["expedient_id"]
                exp = self.env["fund.expedient"].browse(exp_id)
                counters.setdefault(exp_id, 0)
                base = max_by_exp.get(exp_id, 0)
                counters[exp_id] += 1
                next_seq = base + counters[exp_id]
                vals["sequence_in_expedient"] = next_seq
                exp_number = (exp.number or "").strip()
                vals["number"] = f"{exp_number}-{next_seq:03d}" if exp_number else f"{next_seq:03d}"

        return super().create(vals_list)
