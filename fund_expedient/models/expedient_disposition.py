# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FundExpedientDisposition(models.Model):
    _name = "fund.expedient.disposition"
    _description = "Disposición del expediente"
    _order = "sequence, id"

    # Expediente y etapa son OPCIONALES: una disposición puede cargarse suelta
    # desde su propio menú (trámite administrativo que todavía no corresponde a
    # un expediente) y vincularse más adelante. Dentro de un expediente el
    # circuito no cambia.
    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        ondelete="cascade",
        index=True,
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.context.get("default_stage_id"),
    )
    file_data = fields.Binary(string="Archivo", attachment=True)
    file_name = fields.Char(string="Nombre archivo")
    expedient_allowed_stage_ids = fields.Many2many(
        "fund.expedient.stage",
        compute="_compute_expedient_allowed_stage_ids",
        string="Etapas del expediente",
        help="Campo técnico: acota el selector de etapa a las del expediente elegido.",
    )

    @api.depends("expedient_id", "expedient_id.type_id")
    def _compute_expedient_allowed_stage_ids(self):
        Stage = self.env["fund.expedient.stage"]
        for rec in self:
            if not rec.expedient_id:
                rec.expedient_allowed_stage_ids = Stage
                continue
            expedient_type = rec.expedient_id.type_id
            if expedient_type and expedient_type.stage_assign_ids:
                rec.expedient_allowed_stage_ids = expedient_type.stage_assign_ids.mapped(
                    "stage_id"
                )
            else:
                rec.expedient_allowed_stage_ids = Stage.search(
                    [("company_id", "in", [False, rec.expedient_id.company_id.id])]
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
    disposition_date = fields.Date(
        string="Fecha de Disposición",
        default=fields.Date.context_today,
        help="Fecha asociada a la disposición. Por defecto se propone la fecha de hoy.",
    )
    disposition_type_id = fields.Many2one(
        "fund.expedient.disposition.type",
        string="Tipo de disposición",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.ref(
            "fund_expedient.disposition_type_adjudicacion", raise_if_not_found=False
        ),
        help="Los tipos que NO cierran el expediente (p. ej. Adjudicación) dejan que el "
        "proceso siga con las etapas siguientes. Los que sí cierran llevan el expediente "
        "a la etapa del flujo marcada con ese mismo resultado final.",
    )
    disposition_closes_expedient = fields.Boolean(
        related="disposition_type_id.closes_expedient",
        string="Cierra el expediente",
    )
    outcome_applied = fields.Boolean(
        string="Resultado aplicado",
        compute="_compute_outcome_applied",
        help="True si el expediente ya está en la etapa final que corresponde a esta disposición.",
    )

    @api.depends(
        "disposition_type_id",
        "disposition_type_id.closes_expedient",
        "expedient_id.stage_id",
        "expedient_id.stage_id.final_outcome_type_id",
    )
    def _compute_outcome_applied(self):
        for rec in self:
            rec.outcome_applied = bool(
                rec.disposition_type_id.closes_expedient
                and rec.expedient_id
                and rec.expedient_id.stage_id.final_outcome_type_id
                == rec.disposition_type_id
            )

    def action_apply_disposition(self):
        """Cierra el expediente en la etapa final según el tipo de disposición.

        Solo aplica para Desierto / Sin efecto / Fracasado; con Adjudicación el
        flujo sigue su curso normal y este botón no está disponible.
        """
        for rec in self:
            if not rec.expedient_id:
                raise UserError(
                    _(
                        "La disposición %s no está vinculada a ningún expediente: "
                        "no hay nada que cerrar. Asigne el expediente primero."
                    )
                    % (rec.number or "")
                )
            if rec.cancelled:
                raise UserError(
                    _(
                        "La disposición %s está anulada: no puede aplicarse para "
                        "cerrar el expediente."
                    )
                    % (rec.number or "")
                )
            if not rec.disposition_type_id.closes_expedient:
                raise UserError(
                    _(
                        "El tipo «%s» no cierra el expediente: el proceso continúa "
                        "con las etapas siguientes."
                    )
                    % (rec.disposition_type_id.name or "")
                )
            rec.expedient_id._apply_disposition_outcome(
                rec.disposition_type_id, disposition=rec
            )
        return True
    name = fields.Char(
        string="Disposición",
        compute="_compute_name",
        store=True,
    )
    notes = fields.Html(string="Observaciones", sanitize="email_outgoing")

    document_ids = fields.One2many(
        "fund.expedient.document",
        "disposition_id",
        string="Documentos relacionados",
        readonly=True,
    )
    # Campo propio (ya no related): una disposición suelta no tiene expediente
    # del cual heredar la compañía. Cuando hay expediente, `create` la toma de él.
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
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
            if not rec.expedient_id:
                # Disposición suelta: no hay etapa que gobierne el permiso, así
                # que se rige solo por los permisos del modelo. Si diera False
                # quedaría imposible de anular o de enviar a aprobación.
                rec.expedient_stage_editable = True
                continue
            rec.expedient_stage_editable = bool(rec.expedient_id.can_edit_in_stage)

    cancelled = fields.Boolean(
        string="Anulada",
        readonly=True,
        copy=False,
        index=True,
        help="Una disposición anulada queda como historial: no cuenta para los "
        "requisitos de la etapa y permite crear otra en su lugar.",
    )
    cancel_date = fields.Date(string="Fecha de anulación", readonly=True, copy=False)

    def action_cancel(self):
        """Anula la disposición para poder crear otra en su lugar.

        No se borra: conserva su número y sus aprobaciones cerradas como
        historial, y deja de contar para los requisitos de la etapa.
        """
        for rec in self:
            if rec.cancelled:
                raise UserError(_("La disposición %s ya está anulada.") % (rec.number or ""))
            if not rec.expedient_stage_editable:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual del expediente "
                        "pueden anular la disposición."
                    )
                )
            rec._cancel_pending_approvals()
            rec.with_context(skip_validation_check=True).write(
                {"cancelled": True, "cancel_date": fields.Date.context_today(rec)}
            )
            if rec.expedient_id:
                rec.expedient_id.message_post(
                    body=_(
                        "Se anuló la disposición <b>%s</b>. Puede crearse otra.",
                        rec.number or "",
                    ),
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

            # Con expediente, la compañía se hereda de él; sin expediente queda
            # la de la sesión (default del campo).
            if exp_id and not vals.get("company_id"):
                exp_company = self.env["fund.expedient"].browse(exp_id).company_id
                if exp_company:
                    vals["company_id"] = exp_company.id

            if exp_id and stage_id:
                exp = self.env["fund.expedient"].browse(exp_id)
                if exp.type_id:
                    assign = Assign.search(
                        [("type_id", "=", exp.type_id.id), ("stage_id", "=", stage_id)],
                        limit=1,
                    )
                    if assign and not assign.require_disposition:
                        raise ValidationError(
                            "La etapa seleccionada no requiere disposición; no puede crear una en este contexto."
                        )

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
                vals["number"] = seq_env.next_by_code("fund.expedient.disposition") or "/"

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

