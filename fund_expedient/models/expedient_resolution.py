# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    resolution_date = fields.Date(
        string="Fecha de Resolución",
        default=fields.Date.context_today,
        help="Fecha asociada a la resolución. Por defecto se propone la fecha de hoy.",
    )
    name = fields.Char(
        string="Resolución",
        compute="_compute_name",
        store=True,
    )
    notes = fields.Html(string="Observaciones", sanitize="email_outgoing")

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

    # Quién puede operar este registro: se hereda de la etapa actual del
    # expediente. Gobierna la cancelación y el reinicio de la validación, y la
    # visibilidad de esos botones.
    expedient_stage_editable = fields.Boolean(
        string="Opera la etapa del expediente",
        compute="_compute_expedient_stage_editable",
    )

    @api.depends("expedient_id.can_edit_in_stage")
    @api.depends_context("uid")
    def _compute_expedient_stage_editable(self):
        for rec in self:
            rec.expedient_stage_editable = bool(
                rec.expedient_id and rec.expedient_id.can_edit_in_stage
            )

    cancelled = fields.Boolean(
        string="Anulada",
        readonly=True,
        copy=False,
        index=True,
        help="Una resolución anulada queda como historial: no cuenta para los "
        "requisitos de la etapa y permite crear otra en su lugar.",
    )
    cancel_date = fields.Date(string="Fecha de anulación", readonly=True, copy=False)

    def action_cancel(self):
        """Anula la resolución para poder crear otra en su lugar.

        No se borra: conserva su número y sus aprobaciones cerradas como
        historial, y deja de contar para los requisitos de la etapa.
        """
        for rec in self:
            if rec.cancelled:
                raise UserError(_("La resolución %s ya está anulada.") % (rec.number or ""))
            if not rec.expedient_stage_editable:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual del expediente "
                        "pueden anular la resolución."
                    )
                )
            rec._cancel_pending_approvals()
            rec.with_context(skip_validation_check=True).write(
                {"cancelled": True, "cancel_date": fields.Date.context_today(rec)}
            )
            rec.expedient_id.message_post(
                body=_("Se anuló la resolución <b>%s</b>. Puede crearse otra.", rec.number or ""),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _cancel_pending_approvals(self):
        """Hook: al anular, limpiar aprobaciones abiertas.

        En el módulo base no hay validaciones; `expedient_tier_validation` lo
        sobreescribe para eliminar las revisiones pendientes.
        """
        return True



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

            if exp_id and stage_id:
                exp = self.env["fund.expedient"].browse(exp_id)
                if exp.type_id:
                    assign = Assign.search(
                        [("type_id", "=", exp.type_id.id), ("stage_id", "=", stage_id)],
                        limit=1,
                    )
                    if assign and not assign.require_resolution:
                        raise ValidationError(
                            "La etapa seleccionada no requiere resolución; no puede crear una en este contexto."
                        )

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

        records = super().create(vals_list)
        # Resolver placeholders dinámicos (nodos qweb <t t-out="object.campo">)
        # en Observaciones contra el expediente vinculado ('object' = el expediente).
        for rec in records:
            exp = rec.expedient_id
            if exp and exp._html_has_dynamic_placeholders(rec.notes):
                rendered = exp._render_dynamic_template_value(rec.notes)
                if rendered and rendered != rec.notes:
                    rec.notes = rendered
        return records

    @api.depends("number", "stage_id.name")
    def _compute_name(self):
        for rec in self:
            stg = rec.stage_id.name or ""
            rec.name = f"{rec.number} ({stg})" if stg and rec.number else (rec.number or "")

