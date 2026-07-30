# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
    # Tipo de documento (catálogo configurable). Reemplaza a los antiguos booleanos
    # `is_technical_spec` / `is_particular_conditions`, que ahora son atributos del
    # tipo. Queda opcional porque hay documentos históricos sin tipo asignado.
    document_type_id = fields.Many2one(
        "fund.expedient.document.type",
        string="Tipo de documento",
        index=True,
        ondelete="restrict",
        help="Tipo del documento. Las etapas del tipo de expediente pueden exigir "
        "que se suba un documento de determinados tipos para poder avanzar.",
    )
    notes = fields.Html(string="Observaciones")
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
    resolution_id = fields.Many2one(
        "fund.expedient.resolution",
        string="Resolución",
        ondelete="set null",
        domain="[('expedient_id', '=', expedient_id), ('stage_id', '=', stage_id)]",
        help="Si existe una resolución para la etapa, el documento puede asociarse a ella.",
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

    can_download_file = fields.Boolean(
        compute="_compute_stage_permissions",
        store=False,
    )
    can_unlink_file = fields.Boolean(
        compute="_compute_stage_permissions",
        store=False,
    )
    can_edit_document = fields.Boolean(
        compute="_compute_stage_permissions",
        store=False,
        help="True solo si el documento pertenece a la etapa actual del expediente y el "
        "usuario está asignado a esa etapa. Si es False, el documento es de consulta: "
        "no puede modificarse ningún dato.",
    )
    # Los selectores de Disposición / Resolución solo tienen sentido si la etapa
    # ORIGEN del documento las exige. Se mira la etapa del documento (no la actual
    # del expediente) para que un documento viejo siga mostrando su vínculo.
    stage_requires_disposition = fields.Boolean(
        compute="_compute_stage_requirements",
        store=False,
    )
    stage_requires_resolution = fields.Boolean(
        compute="_compute_stage_requirements",
        store=False,
    )

    @api.depends(
        "stage_id",
        "expedient_id.type_id",
        "expedient_id.type_id.stage_assign_ids.stage_id",
        "expedient_id.type_id.stage_assign_ids.require_disposition",
        "expedient_id.type_id.stage_assign_ids.require_resolution",
    )
    def _compute_stage_requirements(self):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            rec.stage_requires_disposition = False
            rec.stage_requires_resolution = False
            expedient_type = rec.expedient_id.type_id
            if not expedient_type or not rec.stage_id:
                continue
            assign = Assign.search(
                [
                    ("type_id", "=", expedient_type.id),
                    ("stage_id", "=", rec.stage_id.id),
                ],
                limit=1,
            )
            if not assign:
                continue
            rec.stage_requires_disposition = assign.require_disposition
            rec.stage_requires_resolution = assign.require_resolution

    @api.depends("expedient_id", "expedient_id.stage_id", "expedient_id.can_edit_in_stage", "stage_id")
    @api.depends_context("uid")
    def _compute_stage_permissions(self):
        for rec in self:
            rec.can_download_file = False
            rec.can_unlink_file = False
            rec.can_edit_document = False
            if not rec.expedient_id or not rec.stage_id:
                continue
            is_current_stage = rec.expedient_id.stage_id == rec.stage_id
            can_manage = bool(is_current_stage and rec.expedient_id.can_edit_in_stage)
            rec.can_download_file = can_manage
            rec.can_unlink_file = can_manage
            rec.can_edit_document = can_manage

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
            # Resolver etapa origen (prioridad): contexto -> disposición -> expediente.
            if not vals.get("stage_id"):
                default_stage_id = self.env.context.get("default_stage_id")
                if default_stage_id:
                    vals["stage_id"] = default_stage_id
            if not vals.get("stage_id") and vals.get("disposition_id"):
                disp = self.env["fund.expedient.disposition"].browse(vals["disposition_id"])
                if disp and disp.stage_id:
                    vals["stage_id"] = disp.stage_id.id
            if not vals.get("stage_id") and vals.get("resolution_id"):
                res = self.env["fund.expedient.resolution"].browse(vals["resolution_id"])
                if res and res.stage_id:
                    vals["stage_id"] = res.stage_id.id
            if not vals.get("stage_id") and vals.get("expedient_id"):
                exp = self.env["fund.expedient"].browse(vals["expedient_id"])
                if exp and exp.stage_id:
                    vals["stage_id"] = exp.stage_id.id

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

            # Si existe una única resolución para el expediente+etapa, autovincular.
            if vals.get("expedient_id") and vals.get("stage_id") and not vals.get("resolution_id"):
                res = self.env["fund.expedient.resolution"].search(
                    [
                        ("expedient_id", "=", vals["expedient_id"]),
                        ("stage_id", "=", vals["stage_id"]),
                    ],
                    order="sequence, id",
                    limit=2,
                )
                if len(res) == 1:
                    vals["resolution_id"] = res.id

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

        self._check_create_allowed(vals_list)
        return super().create(vals_list)

    def _check_create_allowed(self, vals_list):
        """Solo se pueden cargar documentos en la etapa actual, estando asignado.

        Se valida acá (y no solo con `readonly` en la vista) para que el guard
        aplique también a importaciones y RPC. Se ejecuta después de resolver
        `stage_id`, para comparar contra la etapa definitiva.
        """
        if self.env.context.get("skip_document_stage_check"):
            return
        Expedient = self.env["fund.expedient"]
        for vals in vals_list:
            exp_id = vals.get("expedient_id")
            if not exp_id:
                continue
            exp = Expedient.browse(exp_id)
            if not exp.exists():
                continue
            if not exp.can_edit_in_stage:
                raise UserError(
                    _(
                        "No puede cargar documentos en el expediente %(number)s: solo los "
                        "usuarios asignados a la etapa «%(stage)s» pueden hacerlo.",
                        number=exp.number or "",
                        stage=exp.stage_id.name or "",
                    )
                )
            stage_id = vals.get("stage_id")
            if stage_id and exp.stage_id and stage_id != exp.stage_id.id:
                raise UserError(
                    _(
                        "Los documentos se cargan en la etapa actual del expediente "
                        "(«%(current)s»). No puede crear un documento en otra etapa.",
                        current=exp.stage_id.name or "",
                    )
                )

    def write(self, vals):
        """Un documento solo puede modificarse desde su propia etapa.

        Al abrirlo estando el expediente en otra etapa (o sin ser usuario asignado)
        queda de consulta: ningún campo puede cambiarse. El `readonly` de la vista
        ya lo refleja, pero el guard acá cubre importaciones, RPC y escrituras desde
        otras vistas. El contexto `skip_document_stage_check` lo saltea para
        escrituras internas del propio flujo (autovínculos, migraciones).
        """
        if not self.env.context.get("skip_document_stage_check"):
            for rec in self:
                if not rec.can_edit_document:
                    raise UserError(
                        _(
                            "El documento «%(doc)s» pertenece a la etapa «%(stage)s» y no "
                            "puede modificarse: el expediente está en la etapa «%(current)s». "
                            "Los documentos solo se editan desde su propia etapa.",
                            doc=rec.name or rec.number or "",
                            stage=rec.stage_id.name or "",
                            current=rec.expedient_id.stage_id.name or "",
                        )
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if not rec.can_unlink_file:
                raise UserError(
                    _(
                        "Solo puede eliminar documentos de la etapa actual cuando está asignado a esa etapa."
                    )
                )
        return super().unlink()

    def action_download_file(self):
        self.ensure_one()
        if not self.can_download_file:
            raise UserError(
                _(
                    "Solo puede descargar documentos de la etapa actual cuando está asignado a esa etapa."
                )
            )
        # Descarga controlada por etapa: el controlador fuerza inline si no corresponde.
        return {
            "type": "ir.actions.act_url",
            "url": f"/fund_expedient/document/download/{self.id}?download=1",
            "target": "self",
        }

    def action_preview_file(self):
        self.ensure_one()
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("res_field", "=", "file_data"),
            ],
            limit=1,
        )
        return {
            "type": "ir.actions.client",
            "tag": "fund_expedient.document_file_viewer",
            "params": {
                "attachmentId": attachment.id,
                "filename": self.file_name or self.name or _("Documento"),
                "mimetype": attachment.mimetype or "application/octet-stream",
                "canDownload": bool(self.can_download_file),
            },
        }

    def action_open_document(self):
        """Abrir el documento (mismo registro que en la solapa del expediente)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documento"),
            "res_model": "fund.expedient.document",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
