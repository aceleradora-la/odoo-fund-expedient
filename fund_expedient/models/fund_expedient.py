# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo import _
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _description = "Expediente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "number"
    _rec_names_search = ["number", "description_plain"]

    number = fields.Char(
        string="Número",
        copy=False,
        readonly=True,
        index=True,
    )
    @api.model
    def _default_requestor_id(self):
        employee = self.env["hr.employee"].search(
            [
                ("user_id", "=", self.env.uid),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            order="company_id desc, id",
            limit=1,
        )
        return employee.id if employee else False

    request_date = fields.Date(
        string="Fecha de solicitud",
        default=fields.Date.context_today,
        tracking=True,
    )
    estimated_need_date = fields.Date(
        string="Fecha estimada de la necesidad",
        tracking=True,
    )
    # Compatibilidad: mantenemos el campo legacy (Many2one) y migramos a multi-proveedor.
    recommended_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor recomendado (legacy)",
        tracking=True,
        domain=[("is_company", "=", True)],
        help="Campo legacy. Use 'Proveedores recomendados'.",
    )
    recommended_supplier_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="fund_expedient_recommended_supplier_rel",
        column1="expedient_id",
        column2="partner_id",
        string="Proveedores recomendados",
        tracking=True,
        domain=[("is_company", "=", True)],
        help="Proveedores recomendados generales del expediente (se usan cuando las líneas no definen proveedores).",
    )
    requestor_id = fields.Many2one(
        "hr.employee",
        string="Solicitante",
        required=True,
        default=lambda self: self._default_requestor_id(),
        tracking=True,
    )
    requestor_user_id = fields.Many2one(
        "res.users",
        string="Usuario solicitante",
        related="requestor_id.user_id",
        store=True,
        readonly=True,
        help="Campo técnico para Tier Validation (reviewer field → usuario del solicitante).",
    )
    type_unit_mode = fields.Selection(
        related="type_id.unit_mode",
        string="Unidad de aprobación (tipo)",
        store=True,
        readonly=True,
    )
    approval_currency_id = fields.Many2one(
        related="type_id.approval_currency_id",
        string="Moneda (tipo)",
        store=True,
        readonly=True,
    )
    show_encuadre = fields.Boolean(
        string="Mostrar encuadre",
        compute="_compute_show_flags",
        store=True,
    )
    show_ur_totals = fields.Boolean(
        string="Mostrar totales UR",
        compute="_compute_show_flags",
        store=True,
    )
    show_uf_totals = fields.Boolean(
        string="Mostrar totales UF",
        compute="_compute_show_flags",
        store=True,
    )
    has_dispositions_feature = fields.Boolean(
        string="Usa disposiciones (tipo)",
        compute="_compute_feature_flags",
        store=True,
        help="True si el tipo de expediente configura al menos una etapa con 'Requiere disposición'.",
    )
    has_resolutions_feature = fields.Boolean(
        string="Usa resoluciones (tipo)",
        compute="_compute_feature_flags",
        store=True,
        help="True si el tipo de expediente configura al menos una etapa con 'Requiere resolución'.",
    )
    hide_type_id_stage = fields.Boolean(
        string="Ocultar Tipo por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_encuadre_id_stage = fields.Boolean(
        string="Ocultar Encuadre por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_estimated_need_date_stage = fields.Boolean(
        string="Ocultar Fecha estimada por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_recommended_supplier_id_stage = fields.Boolean(
        string="Ocultar Proveedor recomendado por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_recommended_supplier_ids_stage = fields.Boolean(
        string="Ocultar Proveedores recomendados por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_budget_position_id_stage = fields.Boolean(
        string="Ocultar Partida presupuestaria por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_analytic_account_id_stage = fields.Boolean(
        string="Ocultar Cuenta analítica por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_amount_estimated_stage = fields.Boolean(
        string="Ocultar Total estimado por etapa",
        compute="_compute_stage_field_visibility",
    )
    current_assign_require_disposition = fields.Boolean(
        string="Etapa actual requiere disposición",
        compute="_compute_current_assign_flags",
    )
    current_assign_require_resolution = fields.Boolean(
        string="Etapa actual requiere resolución",
        compute="_compute_current_assign_flags",
    )
    current_assign_require_notification = fields.Boolean(
        string="Etapa actual requiere notificación",
        compute="_compute_current_assign_flags",
    )
    current_stage_notification_template_id = fields.Many2one(
        "mail.template",
        string="Plantilla notificación (etapa)",
        compute="_compute_current_assign_flags",
    )
    line_amounts_drive_estimated = fields.Boolean(
        string="Total estimado viene de líneas",
        compute="_compute_line_amount_flags",
    )
    line_amounts_drive_confirmed = fields.Boolean(
        string="Total definitivo viene de líneas",
        compute="_compute_line_amount_flags",
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria asignada",
        tracking=True,
        domain="[('budget_assignment_allowed', '=', True)]",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        tracking=True,
        domain="[('plan_id', '=', analytic_plan_id), ('company_id', 'in', [False, company_id])]",
        help="Cuenta analítica (del plan configurado para la compañía) usada para imputación y reportes.",
    )
    analytic_plan_id = fields.Many2one(
        "account.analytic.plan",
        compute="_compute_analytic_plan_id",
        store=False,
        string="Plan analítico (config)",
    )
    encuadre_id = fields.Many2one(
        "fund.expedient.encuadre",
        string="Encuadre",
        tracking=True,
        domain="[('id', 'in', type_id and type_id.encuadre_ids.ids or [])]",
    )
    type_id = fields.Many2one(
        "fund.expedient.type",
        string="Tipo",
        tracking=True,
    )
    description = fields.Html(
        string="Descripción/Memo",
    )
    description_plain = fields.Text(
        string="Descripción (texto)",
        compute="_compute_description_plain",
        store=True,
        index=True,
        help="Versión en texto plano de la descripción HTML, usada para búsquedas y vistas resumidas (kanban/lista).",
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        group_expand="_read_group_stage_ids",
        tracking=True,
        copy=False,
        ondelete="restrict",
        domain="[('id', 'in', allowed_stage_ids)]",
        default=lambda self: self._default_stage_id(),
    )
    stage_spend_request_mode = fields.Selection(
        related="stage_id.spend_request_mode",
        string="Solicitud de Gasto (etapa)",
        store=True,
        readonly=True,
    )
    allowed_stage_ids = fields.Many2many(
        "fund.expedient.stage",
        compute="_compute_allowed_stage_ids",
        string="Etapas permitidas",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("in_progress", "En progreso"),
            ("purchases", "Compras"),
            ("to_approve", "Por aprobar"),
            ("approved", "Aprobado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        compute="_compute_state",
        store=True,
        tracking=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    # Relación con otros expedientes
    parent_id = fields.Many2one(
        "fund.expedient",
        string="Expediente padre",
        ondelete="set null",
        index=True,
    )
    child_ids = fields.One2many(
        "fund.expedient",
        "parent_id",
        string="Expedientes relacionados",
    )
    line_ids = fields.One2many(
        "fund.expedient.line",
        "expedient_id",
        string="Líneas",
        copy=True,
    )
    document_ids = fields.One2many(
        "fund.expedient.document",
        "expedient_id",
        string="Documentos por etapa",
        copy=False,
    )
    disposition_ids = fields.One2many(
        "fund.expedient.disposition",
        "expedient_id",
        string="Disposiciones",
        copy=False,
    )
    resolution_ids = fields.One2many(
        "fund.expedient.resolution",
        "expedient_id",
        string="Resoluciones",
        copy=False,
    )
    spend_request_ids = fields.One2many(
        "fund.expedient.spend.request",
        "expedient_id",
        string="Solicitudes de Gasto",
        copy=False,
    )
    notification_mail_ids = fields.One2many(
        "fund.expedient.notification.mail",
        "expedient_id",
        string="Notificaciones enviadas",
        readonly=True,
    )
    # Relaciones con Purchase y Project (many2many: un expediente puede tener muchas)
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "fund_expedient_purchase_order_rel",
        "expedient_id",
        "order_id",
        string="Solicitudes de cotización",
        copy=False,
    )
    purchase_order_count = fields.Integer(
        compute="_compute_purchase_order_count",
        string="Nº Solicitudes",
    )
    can_create_purchase = fields.Boolean(
        compute="_compute_can_create_purchase",
        string="Puede crear solicitudes",
    )
    can_edit_in_stage = fields.Boolean(
        string="Puede editar en etapa",
        compute="_compute_can_edit_in_stage",
        help="True si el usuario actual puede modificar el expediente en la etapa actual (asignación tipo/etapa).",
    )
    assignable_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_assignable_user_ids",
        store=True,
        string="Usuarios asignables (etapa)",
        help="Usuarios que pueden operar en la etapa actual según la configuración del tipo/etapa. "
        "Se almacena para poder filtrar expedientes 'asignados a mí' desde la búsqueda.",
    )
    project_ids = fields.Many2many(
        "project.project",
        "fund_expedient_project_rel",
        "expedient_id",
        "project_id",
        string="Proyectos",
        copy=False,
    )
    project_count = fields.Integer(
        compute="_compute_project_count",
        string="Nº Proyectos",
    )
    payment_ids = fields.Many2many(
        "account.payment",
        compute="_compute_payment_ids",
        string="Pagos",
        copy=False,
        help="Pagos relacionados: por vinculación directa, por factura directa "
        "o por factura de orden de compra.",
    )
    payment_count = fields.Integer(
        compute="_compute_payment_ids",
        string="Nº Pagos",
    )
    direct_invoice_ids = fields.Many2many(
        "account.move",
        "fund_expedient_account_move_rel",
        "expedient_id",
        "move_id",
        string="Facturas directas",
        copy=False,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund'))]",
        help="Facturas de proveedor sin orden de compra. "
        "Las facturas desde OC se vinculan automáticamente.",
    )
    invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_invoice_ids",
        string="Facturas",
        copy=False,
        help="Facturas de proveedor: desde órdenes de compra o directas.",
    )
    invoice_count = fields.Integer(
        compute="_compute_invoice_ids",
        string="Nº Facturas",
    )

    # Totales (moneda compañía y UR)
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moneda",
    )
    amount_estimated_manual = fields.Monetary(
        string="Total estimado (manual)",
        currency_field="currency_id",
        tracking=True,
        help="Se usa cuando no hay líneas de detalle con importes; si hay líneas, el total estimado es la suma.",
    )
    amount_estimated = fields.Monetary(
        string="Total Estimado",
        currency_field="currency_id",
        compute="_compute_amount_estimated_total",
        inverse="_inverse_amount_estimated_total",
        store=True,
        tracking=True,
    )
    amount_committed = fields.Monetary(
        string="Total Comprometido",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_real = fields.Monetary(
        string="Total Real",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_estimated_unit = fields.Monetary(
        string="Total Estimado (moneda tipo)",
        compute="_compute_amounts_unit",
        store=True,
        currency_field="approval_currency_id",
        help="Total estimado expresado en la moneda configurada en el Tipo de Expediente.",
    )
    amount_committed_unit = fields.Monetary(
        string="Total Comprometido (moneda tipo)",
        compute="_compute_amounts_unit",
        store=True,
        currency_field="approval_currency_id",
        help="Total comprometido expresado en la moneda configurada en el Tipo de Expediente.",
    )
    amount_real_unit = fields.Monetary(
        string="Total Real (moneda tipo)",
        compute="_compute_amounts_unit",
        store=True,
        currency_field="approval_currency_id",
        help="Total real expresado en la moneda configurada en el Tipo de Expediente.",
    )
    amount_estimated_confirmed_manual = fields.Monetary(
        string="Importe definitivo (manual)",
        currency_field="currency_id",
        tracking=True,
        help="Si hay líneas con importe definitivo, el total definitivo es la suma de las líneas.",
    )
    amount_estimated_confirmed = fields.Monetary(
        string="Total Estimado Confirmado",
        currency_field="currency_id",
        compute="_compute_amount_estimated_confirmed_total",
        inverse="_inverse_amount_estimated_confirmed_total",
        store=True,
        tracking=True,
        help="Total confirmado (moneda compañía) usado para Solicitud de Gasto definitiva.",
    )
    amount_estimated_confirmed_unit = fields.Monetary(
        string="Total Estimado Confirmado (moneda tipo)",
        compute="_compute_amount_estimated_confirmed_unit",
        store=True,
        currency_field="approval_currency_id",
        help="Total confirmado expresado en la moneda configurada en el Tipo de Expediente.",
    )
    report_count = fields.Integer(
        string="Cantidad",
        compute="_compute_report_count",
        store=True,
        help="Siempre 1; para usar como medida de conteo en reportes y tableros.",
    )

    @api.depends("create_date")
    def _compute_report_count(self):
        for rec in self:
            rec.report_count = 1

    @api.model
    def _default_stage_id(self):
        return self._get_default_draft_stage().id

    def _get_default_draft_stage(self, company=None):
        """Etapa borrador por defecto (fallback global).

        Nota: no todos los tipos incluyen una etapa de estado 'draft'. Esta etapa
        solo se usa como fallback cuando el expediente no tiene tipo o el tipo
        no define asignaciones por etapa.
        """
        company = company or self.env.company
        return self.env["fund.expedient.stage"].search(
            [
                ("state_type", "=", "draft"),
                ("company_id", "in", [False, company.id]),
            ],
            order="sequence, id",
            limit=1,
        )

    def _get_initial_stage_for_type(self, expedient_type, company=None):
        """Devuelve la etapa inicial válida para un tipo.

        Regla: si el tipo define `stage_assign_ids`, la etapa inicial es la primera
        (por sequence) dentro de esas asignaciones. Si no define, se usa borrador.
        """
        company = company or self.env.company
        if expedient_type and expedient_type.stage_assign_ids:
            stages = (
                expedient_type.stage_assign_ids.mapped("stage_id")
                .filtered(lambda s: s.company_id in (False, company))
                .sorted(key=lambda s: (s.sequence, s.id))
            )
            return stages[:1]
        return self._get_default_draft_stage(company=company)

    @api.depends("stage_id", "stage_id.state_type")
    def _compute_state(self):
        for rec in self:
            if rec.stage_id:
                rec.state = rec.stage_id.state_type or "draft"
            else:
                rec.state = "draft"

    @api.depends("state", "type_id", "type_id.unit_mode")
    def _compute_show_flags(self):
        for rec in self:
            rec.show_encuadre = rec.state == "purchases"
            rec.show_ur_totals = rec.type_unit_mode != "uf"
            rec.show_uf_totals = rec.type_unit_mode == "uf"

    @api.depends("type_id", "type_id.stage_assign_ids", "type_id.stage_assign_ids.require_disposition", "type_id.stage_assign_ids.require_resolution")
    def _compute_feature_flags(self):
        for rec in self:
            assigns = rec.type_id.stage_assign_ids if rec.type_id else self.env["fund.expedient.type.stage.assign"]
            rec.has_dispositions_feature = bool(assigns.filtered(lambda a: a.require_disposition))
            rec.has_resolutions_feature = bool(assigns.filtered(lambda a: a.require_resolution))

    @api.depends(
        "type_id",
        "stage_id",
        "type_id.stage_assign_ids",
        "type_id.stage_assign_ids.hide_type_id",
        "type_id.stage_assign_ids.hide_encuadre_id",
        "type_id.stage_assign_ids.hide_estimated_need_date",
        "type_id.stage_assign_ids.hide_recommended_supplier_id",
        "type_id.stage_assign_ids.hide_budget_position_id",
        "type_id.stage_assign_ids.hide_amount_estimated",
    )
    def _compute_stage_field_visibility(self):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            rec.hide_type_id_stage = False
            rec.hide_encuadre_id_stage = False
            rec.hide_estimated_need_date_stage = False
            rec.hide_recommended_supplier_id_stage = False
            rec.hide_recommended_supplier_ids_stage = False
            rec.hide_budget_position_id_stage = False
            rec.hide_analytic_account_id_stage = False
            rec.hide_amount_estimated_stage = False
            if not rec.type_id or not rec.stage_id:
                continue
            assign = Assign.search(
                [
                    ("type_id", "=", rec.type_id.id),
                    ("stage_id", "=", rec.stage_id.id),
                ],
                limit=1,
            )
            if not assign:
                continue
            rec.hide_type_id_stage = assign.hide_type_id
            rec.hide_encuadre_id_stage = assign.hide_encuadre_id
            rec.hide_estimated_need_date_stage = assign.hide_estimated_need_date
            rec.hide_recommended_supplier_id_stage = assign.hide_recommended_supplier_id
            rec.hide_recommended_supplier_ids_stage = assign.hide_recommended_supplier_id
            rec.hide_budget_position_id_stage = assign.hide_budget_position_id
            # Reutilizamos el mismo flag de ocultación para la nueva cuenta analítica.
            rec.hide_analytic_account_id_stage = assign.hide_budget_position_id
            rec.hide_amount_estimated_stage = assign.hide_amount_estimated

    @api.depends(
        "type_id",
        "stage_id",
        "type_id.stage_assign_ids",
        "type_id.stage_assign_ids.require_disposition",
        "type_id.stage_assign_ids.require_resolution",
        "type_id.stage_assign_ids.require_notification",
        "type_id.stage_assign_ids.notification_template_id",
    )
    def _compute_current_assign_flags(self):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            rec.current_assign_require_disposition = False
            rec.current_assign_require_resolution = False
            rec.current_assign_require_notification = False
            rec.current_stage_notification_template_id = False
            if not rec.type_id or not rec.stage_id:
                continue
            assign = Assign.search(
                [
                    ("type_id", "=", rec.type_id.id),
                    ("stage_id", "=", rec.stage_id.id),
                ],
                limit=1,
            )
            if assign:
                rec.current_assign_require_disposition = assign.require_disposition
                rec.current_assign_require_resolution = assign.require_resolution
                rec.current_assign_require_notification = bool(assign.require_notification)
                rec.current_stage_notification_template_id = assign.notification_template_id

    @api.depends(
        "line_ids",
        "line_ids.display_type",
        "line_ids.amount_estimated_line",
        "line_ids.amount_final_line",
    )
    def _compute_line_amount_flags(self):
        for rec in self:
            detail_lines = rec.line_ids.filtered(lambda l: not l.display_type)
            rec.line_amounts_drive_estimated = bool(detail_lines)
            rec.line_amounts_drive_confirmed = bool(detail_lines)

    @api.depends(
        "line_ids",
        "line_ids.display_type",
        "line_ids.amount_estimated_line",
        "amount_estimated_manual",
    )
    def _compute_amount_estimated_total(self):
        for rec in self:
            detail_lines = rec.line_ids.filtered(lambda l: not l.display_type)
            if detail_lines:
                rec.amount_estimated = sum(detail_lines.mapped("amount_estimated_line"))
            else:
                rec.amount_estimated = rec.amount_estimated_manual or 0.0

    def _inverse_amount_estimated_total(self):
        for rec in self:
            detail_lines = rec.line_ids.filtered(lambda l: not l.display_type)
            if not detail_lines:
                rec.amount_estimated_manual = rec.amount_estimated

    @api.depends(
        "line_ids",
        "line_ids.display_type",
        "line_ids.amount_final_line",
        "amount_estimated_confirmed_manual",
    )
    def _compute_amount_estimated_confirmed_total(self):
        for rec in self:
            detail_lines = rec.line_ids.filtered(lambda l: not l.display_type)
            if detail_lines:
                rec.amount_estimated_confirmed = sum(detail_lines.mapped("amount_final_line"))
            else:
                rec.amount_estimated_confirmed = rec.amount_estimated_confirmed_manual or 0.0

    def _inverse_amount_estimated_confirmed_total(self):
        for rec in self:
            detail_lines = rec.line_ids.filtered(lambda l: not l.display_type)
            if not detail_lines:
                rec.amount_estimated_confirmed_manual = rec.amount_estimated_confirmed

    @api.depends("company_id")
    def _compute_analytic_plan_id(self):
        Config = self.env["fund.expedient.config"]
        for rec in self:
            plan = Config.get_analytic_plan(rec.company_id)
            rec.analytic_plan_id = plan.id if plan else False

    @api.depends(
        "type_id",
        "type_id.stage_assign_ids",
        "type_id.stage_assign_ids.stage_id",
        "type_id.stage_assign_ids.is_final_stage",
        "stage_id",
        "company_id",
    )
    def _compute_allowed_stage_ids(self):
        Stage = self.env["fund.expedient.stage"]
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            if rec.type_id and rec.type_id.stage_assign_ids:
                ordered = rec.type_id.stage_assign_ids.mapped("stage_id").sorted(
                    key=lambda s: (s.sequence, s.id)
                )
                assign = False
                if rec.stage_id:
                    assign = Assign.search(
                        [
                            ("type_id", "=", rec.type_id.id),
                            ("stage_id", "=", rec.stage_id.id),
                        ],
                        limit=1,
                    )
                if (
                    assign
                    and assign.is_final_stage
                    and rec.stage_id
                    and rec.stage_id.id in ordered.ids
                ):
                    idx = ordered.ids.index(rec.stage_id.id)
                    rec.allowed_stage_ids = ordered[: idx + 1]
                else:
                    rec.allowed_stage_ids = ordered
            else:
                rec.allowed_stage_ids = Stage.search(
                    [("company_id", "in", [False, rec.company_id.id])], order="sequence, id"
                )

    @api.onchange("type_id")
    def _onchange_type_id_clear_estimated(self):
        """Al cambiar el tipo, poner a cero el total estimado para que se recalculen
        los totales en la unidad que corresponda al nuevo tipo."""
        if self.type_id:
            self.amount_estimated = 0.0
            if self._is_empty_html(self.description) and not self._is_empty_html(
                self.type_id.default_description
            ):
                self.description = self.type_id.default_description

        # Evitar quedar en una etapa incompatible con el tipo seleccionado.
        if self.type_id:
            allowed = self.type_id.stage_assign_ids.mapped("stage_id")
            if allowed and (not self.stage_id or self.stage_id not in allowed):
                self.stage_id = allowed.sorted(key=lambda s: (s.sequence, s.id))[:1].id

    def _read_group_stage_ids(self, stages, domain):
        """Etapas en kanban / statusbar: ordenadas por secuencia (corrige orden con filtros como Mis expedientes)."""
        rec = self[:1]
        if not rec:
            active_id = self.env.context.get("active_id")
            if active_id:
                rec = self.browse(active_id)
        if rec:
            return rec.allowed_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
        return stages.sorted(key=lambda s: (s.sequence, s.id))

    @api.depends("purchase_order_ids")
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    @api.depends("stage_id", "stage_id.state_type")
    def _compute_can_create_purchase(self):
        for rec in self:
            rec.can_create_purchase = rec.stage_id.state_type == "purchases"

    @api.depends("project_ids")
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def _get_allowed_stages(self):
        """Etapas permitidas para el expediente según su tipo (asignaciones por etapa del tipo)."""
        Stage = self.env["fund.expedient.stage"]
        for rec in self:
            if rec.type_id and rec.type_id.stage_assign_ids:
                allowed = rec.type_id.stage_assign_ids.mapped("stage_id")
                yield rec, allowed.sorted(key=lambda s: (s.sequence, s.id))
            else:
                all_stages = Stage.search(
                    [("company_id", "in", [False, rec.company_id.id])], order="sequence, id"
                )
                yield rec, all_stages

    def _current_stage_assign(self):
        self.ensure_one()
        if not self.type_id or not self.stage_id:
            return self.env["fund.expedient.type.stage.assign"]
        return self.env["fund.expedient.type.stage.assign"].search(
            [
                ("type_id", "=", self.type_id.id),
                ("stage_id", "=", self.stage_id.id),
            ],
            limit=1,
        )

    @api.model
    def _purchase_order_has_quote_response(self, po):
        """Heurística: cotización respondida (precio en líneas o RFQ ya enviada/confirmada)."""
        if po.state == "cancel":
            return False
        if po.state in ("sent", "purchase", "done"):
            return True
        for line in po.order_line:
            if line.display_type:
                continue
            if line.price_unit:
                return True
        return False

    def _purchase_orders_with_response(self):
        self.ensure_one()
        pos = self.purchase_order_ids.filtered(lambda p: p.state != "cancel")
        return pos.filtered(lambda p: self._purchase_order_has_quote_response(p))

    def _get_responded_rfq_partners(self):
        """Partners (oferentes) con cotización respondida en órdenes vinculadas al expediente."""
        self.ensure_one()
        partners = self.env["res.partner"]
        for po in self._purchase_orders_with_response():
            if po.partner_id:
                partners |= po.partner_id
        return partners

    def _notification_stage_satisfied(self):
        """True si no exige notificación o ya se notificó a todos los oferentes requeridos."""
        self.ensure_one()
        assign = self._current_stage_assign()
        if not assign or not assign.require_notification:
            return True
        partners = self._get_responded_rfq_partners()
        if not partners:
            return False
        Log = self.env["fund.expedient.notification.mail"]
        for partner in partners:
            ok = Log.search_count(
                [
                    ("expedient_id", "=", self.id),
                    ("stage_id", "=", self.stage_id.id),
                    ("partner_id", "=", partner.id),
                    ("state", "=", "sent"),
                ]
            )
            if not ok:
                return False
        return True

    def action_open_notification_wizard(self):
        self.ensure_one()
        assign = self._current_stage_assign()
        if not assign or not assign.notification_template_id:
            raise UserError(
                _("Configure plantilla de notificación en el tipo de expediente para esta etapa.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Notificar oferentes"),
            "res_model": "fund.expedient.notification.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_expedient_id": self.id,
                "default_stage_id": self.stage_id.id,
                "default_mail_template_id": assign.notification_template_id.id,
                "default_mail_server_id": assign.notification_mail_server_id.id,
            },
        }

    def action_next_stage(self):
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden pasar a la siguiente."
                    )
                )
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index == -1 or current_index + 1 >= len(stages):
                continue
            assign = rec._current_stage_assign()
            if assign and assign.is_final_stage:
                raise UserError(
                    _(
                        "Este expediente está en una etapa final del flujo. "
                        "No puede avanzar; solo cancelar el expediente si corresponde."
                    )
                )
            if assign and assign.require_notification:
                if not rec._notification_stage_satisfied():
                    if not rec._get_responded_rfq_partners():
                        raise UserError(
                            _(
                                "No hay oferentes con cotización respondida; "
                                "no se puede completar el requisito de notificación para salir de esta etapa."
                            )
                        )
                    raise UserError(
                        _(
                            "Debe notificar a todos los oferentes (correo registrado) antes de pasar de etapa. "
                            "Use el asistente 'Notificar oferentes'."
                        )
                    )
            target = stages[current_index + 1]
            # Integración simple con tier_validation: si existe y aún no está aprobado,
            # primero se envía a aprobar y no se cambia de etapa.
            if hasattr(rec, "request_validation") and rec.state != "approved":
                rec.request_validation()
            else:
                rec.stage_id = target
        return True

    def action_previous_stage(self):
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden volver a la etapa anterior."
                    )
                )
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index <= 0:
                continue
            target = stages[current_index - 1]
            rec.stage_id = target
        return True

    def _compute_payment_ids(self):
        for rec in self:
            # 1. Pagos con vinculación directa
            payments_direct = self.env["account.payment"].search(
                [("expedient_ids", "in", rec.ids)]
            )
            # 2. Facturas del expediente (OC + directas)
            all_invoices = rec.purchase_order_ids.mapped("invoice_ids") | rec.direct_invoice_ids
            # 3. Pagos reconciliados con esas facturas
            payments_via_invoice = all_invoices.mapped("reconciled_payment_ids")
            all_payments = payments_direct | payments_via_invoice
            rec.payment_ids = all_payments
            rec.payment_count = len(all_payments)

    @api.depends("purchase_order_ids", "purchase_order_ids.invoice_ids", "direct_invoice_ids")
    def _compute_invoice_ids(self):
        for rec in self:
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids")
            all_invoices = invoices_po | rec.direct_invoice_ids
            rec.invoice_ids = all_invoices
            rec.invoice_count = len(all_invoices)

    @api.depends(
        "amount_estimated",
        "request_date",
        "company_id",
        "currency_id",
        "approval_currency_id",
        "purchase_order_ids",
        "purchase_order_ids.state",
        "purchase_order_ids.invoice_status",
        "purchase_order_ids.amount_total",
        "purchase_order_ids.date_order",
        "purchase_order_ids.currency_id",
        "purchase_order_ids.invoice_ids",
        "purchase_order_ids.invoice_ids.state",
        "purchase_order_ids.invoice_ids.amount_total_signed",
        "direct_invoice_ids",
        "direct_invoice_ids.state",
        "direct_invoice_ids.amount_total_signed",
    )
    def _compute_amounts_unit(self):
        for rec in self:
            unit_currency = rec.approval_currency_id
            company_currency = rec.company_id.currency_id
            company = rec.company_id

            if not unit_currency:
                rec.amount_estimated_unit = 0.0
                rec.amount_committed_unit = 0.0
                rec.amount_real_unit = 0.0
                continue

            # Estimado: el valor base está en moneda compañía (amount_estimated).
            if rec.amount_estimated and rec.request_date:
                rec.amount_estimated_unit = company_currency._convert(
                    rec.amount_estimated, unit_currency, company, rec.request_date
                )
            else:
                rec.amount_estimated_unit = 0.0

            # Comprometido: mismo criterio del compute actual, pero convertido a moneda del tipo.
            pos_committed = rec.purchase_order_ids.filtered(
                lambda po: po.state in ("purchase", "done") and po.invoice_status != "invoiced"
            )
            committed_unit = 0.0
            for po in pos_committed:
                po_date = po.date_order.date()
                ordered_cc = po.currency_id._convert(po.amount_total, company_currency, company, po_date)
                invoiced_cc = 0.0
                for inv in po.invoice_ids.filtered(lambda m: m.state == "posted"):
                    inv_date = inv.invoice_date or inv.date
                    signed = -inv.amount_total_signed
                    invoiced_cc += inv.currency_id._convert(signed, company_currency, company, inv_date)
                pending_cc = max(0.0, ordered_cc - invoiced_cc)
                committed_unit += company_currency._convert(pending_cc, unit_currency, company, po_date)
            rec.amount_committed_unit = committed_unit

            # Real: facturas posteadas (desde OC o directas) convertido a moneda del tipo por fecha de factura.
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids").filtered(lambda m: m.state == "posted")
            invoices_direct = rec.direct_invoice_ids.filtered(lambda m: m.state == "posted")
            all_invoices = invoices_po | invoices_direct
            real_unit = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                signed = -inv.amount_total_signed
                amt_cc = inv.currency_id._convert(signed, company_currency, company, inv_date)
                real_unit += company_currency._convert(amt_cc, unit_currency, company, inv_date)
            rec.amount_real_unit = real_unit

    @api.depends(
        "amount_estimated_confirmed",
        "request_date",
        "company_id",
        "currency_id",
        "approval_currency_id",
    )
    def _compute_amount_estimated_confirmed_unit(self):
        for rec in self:
            unit_currency = rec.approval_currency_id
            company_currency = rec.company_id.currency_id
            company = rec.company_id
            if not unit_currency or not rec.amount_estimated_confirmed or not rec.request_date:
                rec.amount_estimated_confirmed_unit = 0.0
                continue
            rec.amount_estimated_confirmed_unit = company_currency._convert(
                rec.amount_estimated_confirmed, unit_currency, company, rec.request_date
            )

    @api.depends(
        "purchase_order_ids",
        "purchase_order_ids.state",
        "purchase_order_ids.invoice_status",
        "purchase_order_ids.amount_total",
        "purchase_order_ids.amount_total_cc",
        "purchase_order_ids.date_order",
        "purchase_order_ids.currency_id",
        "purchase_order_ids.order_line",
        "purchase_order_ids.order_line.qty_to_invoice",
        "purchase_order_ids.order_line.product_qty",
        "purchase_order_ids.order_line.price_total",
        "purchase_order_ids.invoice_ids",
        "purchase_order_ids.invoice_ids.state",
        "purchase_order_ids.invoice_ids.amount_total_signed",
        "direct_invoice_ids",
        "direct_invoice_ids.state",
        "direct_invoice_ids.amount_total_signed",
        "company_id",
    )
    def _compute_amounts(self):
        for rec in self:
            company_currency = rec.company_id.currency_id

            # Total Comprometido: OC confirmadas menos facturado (posteado).
            # Nota: con "facturación al recibir", qty_to_invoice puede ser 0 hasta recibir, pero el
            # compromiso debería reflejar el total ordenado desde la confirmación.
            pos_committed = rec.purchase_order_ids.filtered(
                lambda po: po.state in ("purchase", "done")
                and po.invoice_status != "invoiced"
            )
            amount_committed = 0.0
            for po in pos_committed:
                po_date = po.date_order.date()
                ordered_cc = po.currency_id._convert(
                    po.amount_total, company_currency, rec.company_id, po_date
                )
                invoiced_cc = 0.0
                for inv in po.invoice_ids.filtered(lambda m: m.state == "posted"):
                    inv_date = inv.invoice_date or inv.date
                    signed = -inv.amount_total_signed
                    invoiced_cc += inv.currency_id._convert(
                        signed, company_currency, rec.company_id, inv_date
                    )
                pending_cc = max(0.0, ordered_cc - invoiced_cc)
                amount_committed += pending_cc
            rec.amount_committed = amount_committed

            # Total Real: facturas posteadas (desde OC o directas)
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids").filtered(
                lambda m: m.state == "posted"
            )
            invoices_direct = rec.direct_invoice_ids.filtered(
                lambda m: m.state == "posted"
            )
            all_invoices = invoices_po | invoices_direct
            amount_real = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                # amount_total_signed: negativo para facturas, positivo para devoluciones
                signed = -inv.amount_total_signed
                amt_cc = inv.currency_id._convert(
                    signed, company_currency, rec.company_id, inv_date
                )
                amount_real += amt_cc
            rec.amount_real = amount_real

    def write(self, vals):
        """Escritura con 2 reglas:

        - Seguridad: solo usuarios asignados a la etapa actual pueden editar (salvo contexto).
        - Consistencia: tipo y etapa deben ser compatibles; si no, ajustar a la primera etapa permitida.
        """
        needs_stage_guard = "type_id" in vals or "stage_id" in vals or "company_id" in vals

        # Camino rápido: sin cambios de tipo/etapa, conservar comportamiento actual.
        if not needs_stage_guard:
            if not self.env.context.get("skip_validation_check"):
                for rec in self:
                    if not rec.can_edit_in_stage:
                        raise UserError(
                            _(
                                "Solo los usuarios asignados a la etapa actual pueden modificar este expediente."
                            )
                        )
            return super().write(vals)

        Type = self.env["fund.expedient.type"]
        Assign = self.env["fund.expedient.type.stage.assign"]
        skip_check = bool(self.env.context.get("skip_validation_check"))
        for rec in self:
            if not skip_check and not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden modificar este expediente."
                    )
                )

            new_vals = dict(vals)
            company = (
                self.env["res.company"].browse(new_vals["company_id"])
                if new_vals.get("company_id")
                else rec.company_id
            )
            type_id = new_vals.get("type_id") or rec.type_id.id
            expedient_type = Type.browse(type_id) if type_id else False

            if expedient_type and expedient_type.stage_assign_ids:
                allowed = expedient_type.stage_assign_ids.mapped("stage_id")
                target_stage_id = new_vals.get("stage_id") or rec.stage_id.id
                if not target_stage_id or target_stage_id not in allowed.ids:
                    new_vals["stage_id"] = (
                        self._get_initial_stage_for_type(expedient_type, company=company).id
                        or False
                    )

            # Reglas de disposición: al salir de la etapa actual, validar requisitos configurados.
            stage_will_change = (
                "stage_id" in new_vals
                and new_vals.get("stage_id")
                and new_vals.get("stage_id") != rec.stage_id.id
            )
            if stage_will_change and rec.type_id and rec.stage_id and not self.env.context.get(
                "skip_disposition_check"
            ):
                assign_cur = Assign.search(
                    [
                        ("type_id", "=", rec.type_id.id),
                        ("stage_id", "=", rec.stage_id.id),
                    ],
                    limit=1,
                )
                if assign_cur and assign_cur.require_disposition:
                    dispositions = rec.disposition_ids.filtered(lambda d: d.stage_id == rec.stage_id)
                    if not dispositions:
                        raise UserError(
                            _(
                                "Para salir de la etapa '%s' debe existir al menos una Disposición.",
                                rec.stage_id.name,
                            )
                        )
                    if assign_cur.disposition_file_required:
                        docs_with_file = rec.document_ids.filtered(
                            lambda doc: doc.stage_id == rec.stage_id
                            and doc.disposition_id in dispositions
                            and bool(doc.file_data)
                        )
                        if not docs_with_file:
                            raise UserError(
                                _(
                                    "Para salir de la etapa '%s' la Disposición debe tener un archivo adjunto.",
                                    rec.stage_id.name,
                                )
                            )

            # Reglas de resolución: al salir de la etapa actual, validar requisitos configurados.
            if stage_will_change and rec.type_id and rec.stage_id and not self.env.context.get(
                "skip_resolution_check"
            ):
                assign_cur = Assign.search(
                    [
                        ("type_id", "=", rec.type_id.id),
                        ("stage_id", "=", rec.stage_id.id),
                    ],
                    limit=1,
                )
                if assign_cur and assign_cur.require_resolution:
                    resolutions = rec.resolution_ids.filtered(lambda r: r.stage_id == rec.stage_id)
                    if not resolutions:
                        raise UserError(
                            _(
                                "Para salir de la etapa '%s' debe existir al menos una Resolución.",
                                rec.stage_id.name,
                            )
                        )
                    if assign_cur.resolution_file_required:
                        docs_with_file = rec.document_ids.filtered(
                            lambda doc: doc.stage_id == rec.stage_id
                            and doc.resolution_id in resolutions
                            and bool(doc.file_data)
                        )
                        if not docs_with_file:
                            raise UserError(
                                _(
                                    "Para salir de la etapa '%s' la Resolución debe tener un archivo adjunto.",
                                    rec.stage_id.name,
                                )
                            )

            if stage_will_change and rec.type_id and rec.stage_id and not self.env.context.get(
                "skip_notification_check"
            ):
                assign_cur = Assign.search(
                    [
                        ("type_id", "=", rec.type_id.id),
                        ("stage_id", "=", rec.stage_id.id),
                    ],
                    limit=1,
                )
                if assign_cur and assign_cur.require_notification:
                    if not rec._notification_stage_satisfied():
                        if not rec._get_responded_rfq_partners():
                            raise UserError(
                                _(
                                    "No hay oferentes con cotización respondida; "
                                    "no se puede salir de la etapa '%s' con notificación obligatoria."
                                )
                                % rec.stage_id.name
                            )
                        raise UserError(
                            _(
                                "Para salir de la etapa '%s' debe registrar el envío de correo a todos los oferentes."
                            )
                            % rec.stage_id.name
                        )

            if stage_will_change and rec.type_id and rec.stage_id:
                new_stage = self.env["fund.expedient.stage"].browse(new_vals["stage_id"])
                expedient_type = rec.type_id
                if expedient_type.stage_assign_ids:
                    ordered = expedient_type.stage_assign_ids.mapped("stage_id").sorted(
                        key=lambda s: (s.sequence, s.id)
                    )
                    if (
                        rec.stage_id.id in ordered.ids
                        and new_stage.id in ordered.ids
                        and new_stage.state_type != "cancel"
                    ):
                        old_i = ordered.ids.index(rec.stage_id.id)
                        new_i = ordered.ids.index(new_stage.id)
                        if new_i > old_i:
                            assign_old = Assign.search(
                                [
                                    ("type_id", "=", rec.type_id.id),
                                    ("stage_id", "=", rec.stage_id.id),
                                ],
                                limit=1,
                            )
                            if assign_old and assign_old.is_final_stage:
                                raise UserError(
                                    _(
                                        "No puede avanzar desde la etapa final del flujo; "
                                        "solo puede volver a etapas anteriores o cancelar el expediente."
                                    )
                                )

            super(FundExpedient, rec).write(new_vals)
            if stage_will_change:
                rec._notify_stage_assignees()
        return True

    def _notify_stage_assignees(self):
        """Suscribir y notificar a los usuarios asignados a la etapa actual."""
        for rec in self:
            users = rec._get_assignable_user_ids()
            if not users:
                continue
            partners = users.mapped("partner_id").filtered(lambda p: p)
            if partners:
                try:
                    rec.message_subscribe(partner_ids=partners.ids)
                    rec.message_post(
                        body=_(
                            "El expediente está ahora en la etapa <b>%s</b>. "
                            "Los usuarios asignados a esta etapa han sido notificados.",
                            rec.stage_id.name,
                        ),
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception as e:
                    # No bloquear el avance/cambio de etapa por falta de configuración de email.
                    _logger.warning(
                        "No se pudo notificar asignados de etapa para %s (%s): %s",
                        rec.number,
                        rec.id,
                        e,
                    )

    @api.model_create_multi
    def create(self, vals_list):
        Type = self.env["fund.expedient.type"]
        for vals in vals_list:
            if vals.get("number", "/") == "/":
                seq = self.env["ir.sequence"].next_by_code("fund.expedient") or "/"
                vals["number"] = seq
            # Aplicar memo/descripcion por defecto del tipo si no se envió descripción.
            desc = vals.get("description")
            if self._is_empty_html(desc) and vals.get("type_id"):
                expedient_type = Type.browse(vals["type_id"])
                type_desc = expedient_type.default_description or ""
                if not self._is_empty_html(type_desc):
                    vals["description"] = type_desc
            # Si viene type_id y no viene stage_id (o es incompatible), setear una etapa válida.
            if vals.get("type_id"):
                company = (
                    self.env["res.company"].browse(vals["company_id"])
                    if vals.get("company_id")
                    else self.env.company
                )
                expedient_type = Type.browse(vals["type_id"])
                allowed = expedient_type.stage_assign_ids.mapped("stage_id")
                if not vals.get("stage_id"):
                    vals["stage_id"] = self._get_initial_stage_for_type(
                        expedient_type, company=company
                    ).id or False
                elif allowed and vals["stage_id"] not in allowed.ids:
                    vals["stage_id"] = self._get_initial_stage_for_type(
                        expedient_type, company=company
                    ).id or vals["stage_id"]
        return super().create(vals_list)

    @api.depends("description")
    def _compute_description_plain(self):
        for rec in self:
            rec.description_plain = html2plaintext(rec.description or "").strip()

    @api.model
    def _is_empty_html(self, value):
        """Considera vacío HTML sin contenido (p.ej. '<p><br></p>')."""
        if not value:
            return True
        try:
            return not html2plaintext(str(value)).strip()
        except Exception:
            # Fallback: si algo raro llega, tratamos como no vacío para no borrar datos.
            return False

    def _get_or_create_spend_request(self):
        self.ensure_one()
        sr = self.spend_request_ids[:1]
        if sr:
            return sr
        return self.env["fund.expedient.spend.request"].create({"expedient_id": self.id})

    def action_create_spend_request_initial(self):
        self.ensure_one()
        if not self.stage_id or self.stage_id.spend_request_mode != "preventiva":
            raise UserError("La etapa actual no permite crear Solicitud de Gasto preventiva.")
        sr = self._get_or_create_spend_request()
        sr.action_generate_initial()
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitud de Gasto",
            "res_model": "fund.expedient.spend.request",
            "res_id": sr.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_spend_request_final(self):
        self.ensure_one()
        if not self.stage_id or self.stage_id.spend_request_mode != "final":
            raise UserError("La etapa actual no permite crear Solicitud de Gasto definitiva.")
        sr = self._get_or_create_spend_request()
        sr.action_generate_final()
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitud de Gasto",
            "res_model": "fund.expedient.spend.request",
            "res_id": sr.id,
            "view_mode": "form",
            "target": "current",
        }

    def unlink(self):
        raise UserError(
            "No se pueden eliminar expedientes para mantener la secuencia sin huecos. "
            "Use la opción 'Cancelar' para anular un expediente."
        )

    def action_cancel(self):
        """Mover expediente a estado Cancelado."""
        cancel_stage = self.env["fund.expedient.stage"].search(
            [("state_type", "=", "cancel")], limit=1
        )
        if not cancel_stage:
            raise UserError("No existe una etapa de tipo 'Cancelado' configurada.")
        return self.write({"stage_id": cancel_stage.id})

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de cotización",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.purchase_order_ids.ids)],
            "context": {"default_expedient_ids": [(4, self.id)]},
        }
        if not self.can_create_purchase:
            action["views"] = [
                (
                    self.env.ref(
                        "fund_expedient.view_purchase_order_list_expedient_no_create"
                    ).id,
                    "list",
                ),
                (False, "form"),
            ]
        return action

    def action_view_projects(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Proyectos",
            "res_model": "project.project",
            "view_mode": "list,form",
            "domain": [("id", "in", self.project_ids.ids)],
            "context": {"default_expedient_ids": [(4, self.id)]},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Facturas",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {
                "default_expedient_ids": [(4, self.id)],
                "default_move_type": "in_invoice",
            },
        }

    def action_wizard_create_purchase(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Crear solicitudes desde líneas",
            "res_model": "fund.expedient.line.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": "fund.expedient", "active_id": self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Pagos",
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.payment_ids.ids)],
            "context": {
                "default_expedient_ids": [(4, self.id)],
                "default_partner_type": "supplier",
            },
        }

    @api.depends("type_id", "stage_id")
    @api.depends_context("uid")
    def _compute_can_edit_in_stage(self):
        """Solo pueden editar/cambiar etapa los usuarios asignados a la etapa (grupos, puestos, usuarios)."""
        for rec in self:
            if not rec.type_id or not rec.stage_id:
                rec.can_edit_in_stage = True
                continue
            assign = self.env["fund.expedient.type.stage.assign"].search(
                [
                    ("type_id", "=", rec.type_id.id),
                    ("stage_id", "=", rec.stage_id.id),
                ],
                limit=1,
            )
            # Sin asignación para esa etapa => sin restricción
            if not assign:
                rec.can_edit_in_stage = True
                continue
            users = rec._get_assignable_user_ids()
            # Si está configurado "Solicitante", sin usuario vinculado en requestor_id => bloquea.
            if assign.use_requestor and not users:
                rec.can_edit_in_stage = False
                continue
            # Asignación vacía (sin grupos/puestos/usuarios) => sin restricción
            if not users:
                rec.can_edit_in_stage = True
                continue
            rec.can_edit_in_stage = self.env.user in users

    def _get_assignable_user_ids(self):
        """Usuarios que pueden operar en esta etapa (grupos + puestos + usuarios concretos)."""
        self.ensure_one()
        if not self.type_id or not self.stage_id:
            return self.env["res.users"]
        assign = self.env["fund.expedient.type.stage.assign"].search(
            [
                ("type_id", "=", self.type_id.id),
                ("stage_id", "=", self.stage_id.id),
            ],
            limit=1,
        )
        if not assign:
            return self.env["res.users"]
        if assign.use_requestor:
            req_user = self.requestor_id.user_id
            return req_user if req_user else self.env["res.users"]
        user_ids = assign.group_ids.users | assign.user_ids
        if assign.job_ids:
            employees = self.env["hr.employee"].search(
                [("job_id", "in", assign.job_ids.ids)]
            )
            user_ids |= employees.mapped("user_id").filtered(lambda u: u)
        return user_ids

    @api.depends(
        "type_id",
        "stage_id",
        "requestor_id",
        "requestor_id.user_id",
        "type_id.stage_assign_ids",
        "type_id.stage_assign_ids.stage_id",
        "type_id.stage_assign_ids.use_requestor",
        "type_id.stage_assign_ids.group_ids",
        "type_id.stage_assign_ids.user_ids",
        "type_id.stage_assign_ids.job_ids",
    )
    def _compute_assignable_user_ids(self):
        for rec in self:
            # Sin tipo/etapa o sin asignación => sin restricción efectiva: dejamos vacío para no "asignar" masivamente.
            if not rec.type_id or not rec.stage_id:
                rec.assignable_user_ids = [(6, 0, [])]
                continue
            assign = self.env["fund.expedient.type.stage.assign"].search(
                [("type_id", "=", rec.type_id.id), ("stage_id", "=", rec.stage_id.id)],
                limit=1,
            )
            if not assign:
                rec.assignable_user_ids = [(6, 0, [])]
                continue
            users = rec._get_assignable_user_ids()
            rec.assignable_user_ids = [(6, 0, users.ids)]
