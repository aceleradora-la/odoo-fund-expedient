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
    type_number = fields.Char(
        string="Número por tipo",
        copy=False,
        readonly=True,
        index=True,
        help="Numeración según la secuencia configurada en el tipo de expediente.",
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
    # Sector / departamento del empleado solicitante.
    # Almacenado (store=True) para poder usarlo en filtros, agrupaciones y reportes.
    requestor_department_id = fields.Many2one(
        "hr.department",
        string="Sector requirente",
        related="requestor_id.department_id",
        store=True,
        readonly=True,
        index=True,
        help="Departamento del empleado solicitante. Sirve para identificar el sector requirente del expediente.",
    )
    # Responsable del sector (manager del departamento del solicitante).
    requestor_department_manager_id = fields.Many2one(
        "hr.employee",
        string="Responsable del sector",
        related="requestor_id.department_id.manager_id",
        store=True,
        readonly=True,
        index=True,
        help="Manager del departamento del solicitante.",
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
    type_id_editable_in_stage = fields.Boolean(
        string="Tipo editable en etapa",
        compute="_compute_stage_field_visibility",
    )
    line_amount_final_editable = fields.Boolean(
        string="Importe definitivo editable en etapa",
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
    operation_type = fields.Selection(
        related="type_id.operation_type",
        string="Tipo de operación",
        store=True,
        readonly=True,
        help="Gasto o Ingreso, según el tipo de expediente. Determina la fuente de importes reales "
        "(facturas de proveedor vs. de venta) y el signo en el control presupuestario.",
    )
    contract_kind = fields.Selection(
        related="type_id.contract_kind",
        string="Locación",
        store=True,
        readonly=True,
    )
    description = fields.Html(
        string="Descripción/Memo",
        sanitize="email_outgoing",
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
            ("no_award", "Sin adjudicar"),
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
    # Datos descriptivos de la contratación. Se usan tanto en la
    # ficha del expediente como en la Solicitud de Gasto y reportes.
    contract_object = fields.Text(
        string="Objeto de la contratación",
        required=True,
        tracking=True,
        help="Descripción del objeto/alcance de la contratación.",
    )
    delivery_location = fields.Char(
        string="Lugar de Entrega/Ejecución",
        tracking=True,
        help="Lugar físico de entrega de los bienes o ejecución del servicio.",
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
    # Selector auxiliar para vincular un expediente existente como
    # "relacionado" sin disparar la creación de uno nuevo desde el One2many.
    #
    # Debe estar almacenado: los botones type="object" ejecutan el método
    # sobre el registro guardado, y un Many2one store=False puede llegar
    # vacío al servidor aunque el usuario lo haya elegido en la vista.
    child_picker_id = fields.Many2one(
        "fund.expedient",
        string="Vincular expediente existente",
        copy=False,
        help="Elegí un expediente existente y presioná 'Vincular' para agregarlo como relacionado.",
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
        groups="purchase.group_purchase_user",
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
    # ------------------------------------------------------------------
    # Responsable actual ("quién tiene el expediente")
    #
    # No se almacenan: dependen de las tier reviews (otro modelo, que cambia
    # sin escribir el expediente), por lo que almacenarlos exigiría invalidar
    # a mano en cada transición de aprobación. Se recalculan al leer.
    # ------------------------------------------------------------------
    holder_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_holder",
        search="_search_holder_user_ids",
        string="En poder de",
        help="Quién debe actuar sobre el expediente ahora: los aprobadores pendientes "
        "si hay una validación en curso (del expediente o de su Solicitud), o los "
        "usuarios asignados a la etapa actual en caso contrario.",
    )
    holder_reason = fields.Selection(
        selection=[
            ("stage", "Asignado por etapa"),
            ("expedient_approval", "Esperando aprobación del expediente"),
            ("spend_request_approval", "Esperando aprobación de la solicitud"),
        ],
        compute="_compute_holder",
        string="Motivo",
    )
    holder_summary = fields.Char(
        compute="_compute_holder",
        string="Situación actual",
        help="Texto listo para mostrar: motivo + responsables actuales.",
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
        groups="account.group_account_readonly",
        help="Facturas de proveedor sin orden de compra. "
        "Las facturas desde OC se vinculan automáticamente.",
    )
    # Facturas de venta vinculadas (expedientes de ingreso). Comparten la misma
    # tabla de relación que `direct_invoice_ids`, pero el dominio restringe la
    # selección a facturas/notas de crédito de cliente. Los cómputos de importes
    # filtran por `move_type`, de modo que un expediente de gasto y uno de
    # ingreso nunca se contaminan entre sí.
    sale_invoice_ids = fields.Many2many(
        "account.move",
        "fund_expedient_account_move_rel",
        "expedient_id",
        "move_id",
        string="Facturas de venta",
        copy=False,
        domain="[('move_type', 'in', ('out_invoice', 'out_refund'))]",
        groups="account.group_account_readonly",
        help="Facturas de cliente vinculadas al expediente de ingreso.",
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
    can_view_purchase_orders = fields.Boolean(
        compute="_compute_access_views",
        string="Puede ver compras",
    )
    can_view_invoices = fields.Boolean(
        compute="_compute_access_views",
        string="Puede ver facturas",
    )
    can_view_payments = fields.Boolean(
        compute="_compute_access_views",
        string="Puede ver pagos",
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
        "type_id.stage_assign_ids.allow_edit_type_id",
        "type_id.stage_assign_ids.allow_edit_line_amount_final",
        "type_id.stage_assign_ids.hide_encuadre_id",
        "type_id.stage_assign_ids.hide_estimated_need_date",
        "type_id.stage_assign_ids.hide_recommended_supplier_id",
        "type_id.stage_assign_ids.hide_analytic_account_id",
        "type_id.stage_assign_ids.hide_amount_estimated",
    )
    def _compute_stage_field_visibility(self):
        Assign = self.env["fund.expedient.type.stage.assign"]
        for rec in self:
            rec.hide_type_id_stage = False
            rec.type_id_editable_in_stage = True
            rec.line_amount_final_editable = False
            rec.hide_encuadre_id_stage = False
            rec.hide_estimated_need_date_stage = False
            rec.hide_recommended_supplier_id_stage = False
            rec.hide_recommended_supplier_ids_stage = False
            rec.hide_analytic_account_id_stage = False
            rec.hide_amount_estimated_stage = False
            if not rec.id:
                rec.type_id_editable_in_stage = True
                rec.line_amount_final_editable = True
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
            if rec.id:
                rec.type_id_editable_in_stage = bool(assign.allow_edit_type_id)
                rec.line_amount_final_editable = bool(assign.allow_edit_line_amount_final)
            rec.hide_encuadre_id_stage = assign.hide_encuadre_id
            rec.hide_estimated_need_date_stage = assign.hide_estimated_need_date
            rec.hide_recommended_supplier_id_stage = assign.hide_recommended_supplier_id
            rec.hide_recommended_supplier_ids_stage = assign.hide_recommended_supplier_id
            rec.hide_analytic_account_id_stage = assign.hide_analytic_account_id
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
        "type_id.stage_assign_ids.stage_id.final_outcome",
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
                    allowed = ordered[: idx + 1]
                else:
                    allowed = ordered
                # Las etapas de resultado final (Desierto/Sin efecto/Fracasado)
                # no se ofrecen en el statusbar: se llega a ellas solo con la
                # Disposición. Si el expediente YA está en una, se muestra.
                rec.allowed_stage_ids = allowed.filtered(
                    lambda s: not s.final_outcome or s == rec.stage_id
                )
            else:
                stages = Stage.search(
                    [("company_id", "in", [False, rec.company_id.id])], order="sequence, id"
                )
                rec.allowed_stage_ids = stages.filtered(
                    lambda s: not s.final_outcome or s == rec.stage_id
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

    @api.model
    def _user_can_read_purchase_orders(self):
        return self.env["purchase.order"].has_access("read")

    @api.model
    def _user_can_read_account_moves(self):
        return self.env["account.move"].has_access("read")

    @api.model
    def _user_can_read_account_payments(self):
        return self.env["account.payment"].has_access("read")

    @api.depends_context("uid")
    def _compute_access_views(self):
        can_po = self._user_can_read_purchase_orders()
        can_inv = self._user_can_read_account_moves()
        can_pay = self._user_can_read_account_payments()
        for rec in self:
            rec.can_view_purchase_orders = can_po
            rec.can_view_invoices = can_inv
            rec.can_view_payments = can_pay

    def _purchase_order_ids_sql(self):
        if not self.id:
            return []
        self.env.cr.execute(
            """
            SELECT order_id
              FROM fund_expedient_purchase_order_rel
             WHERE expedient_id = %s
            """,
            [self.id],
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _direct_invoice_ids_sql(self):
        if not self.id:
            return []
        self.env.cr.execute(
            """
            SELECT move_id
              FROM fund_expedient_account_move_rel
             WHERE expedient_id = %s
            """,
            [self.id],
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _purchase_orders_data(self):
        """OC vinculadas: respeta ACL; sin permiso de compras usa sudo solo para agregados."""
        self.ensure_one()
        PurchaseOrder = self.env["purchase.order"]
        if self._user_can_read_purchase_orders():
            return self.purchase_order_ids
        return PurchaseOrder.sudo().browse(self._purchase_order_ids_sql())

    def _direct_invoices_data(self):
        """Facturas directas vinculadas (misma regla de ACL que compras/contabilidad)."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        if self._user_can_read_account_moves():
            return self.direct_invoice_ids
        return AccountMove.sudo().browse(self._direct_invoice_ids_sql())

    def _invalidate_commercial_computes(self):
        """Recalcula totales y contadores al cambiar OC/facturas/pagos vinculados."""
        self.modified(
            [
                "purchase_order_count",
                "invoice_ids",
                "payment_ids",
                "amount_committed",
                "amount_real",
                "amount_committed_unit",
                "amount_real_unit",
            ]
        )

    @api.depends_context("uid")
    def _compute_purchase_order_count(self):
        for rec in self:
            if not rec._user_can_read_purchase_orders():
                rec.purchase_order_count = 0
                continue
            rec.purchase_order_count = len(rec._purchase_orders_data())

    @api.depends("stage_id", "stage_id.state_type")
    @api.depends_context("uid")
    def _compute_can_create_purchase(self):
        for rec in self:
            rec.can_create_purchase = (
                rec.stage_id.state_type == "purchases"
                and rec._user_can_read_purchase_orders()
            )

    @api.depends("project_ids")
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def _get_allowed_stages(self):
        """Etapas del flujo SECUENCIAL del expediente según su tipo.

        Excluye las etapas con `final_outcome` (Desierto/Sin efecto/Fracasado):
        son cierres alternativos a los que solo se llega aplicando una
        Disposición; nunca por "Siguiente etapa" ni por el avance del portal.
        """
        Stage = self.env["fund.expedient.stage"]
        for rec in self:
            if rec.type_id and rec.type_id.stage_assign_ids:
                allowed = rec.type_id.stage_assign_ids.mapped("stage_id").filtered(
                    lambda s: not s.final_outcome
                )
                yield rec, allowed.sorted(key=lambda s: (s.sequence, s.id))
            else:
                all_stages = Stage.search(
                    [
                        ("company_id", "in", [False, rec.company_id.id]),
                        ("final_outcome", "=", False),
                    ],
                    order="sequence, id",
                )
                yield rec, all_stages

    def _stage_change_is_forward(self, new_stage):
        """True si la etapa destino está después de la actual en el flujo del tipo."""
        self.ensure_one()
        new_stage_id = new_stage.id if hasattr(new_stage, "id") else int(new_stage)
        if not new_stage_id or not self.stage_id or new_stage_id == self.stage_id.id:
            return False
        for _rec, stages in self._get_allowed_stages():
            ordered_ids = stages.ids
            if self.stage_id.id not in ordered_ids or new_stage_id not in ordered_ids:
                return True
            return ordered_ids.index(new_stage_id) > ordered_ids.index(self.stage_id.id)
        return True

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
        pos = self._purchase_orders_data().filtered(lambda p: p.state != "cancel")
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
            if rec.stage_id.final_outcome:
                raise UserError(
                    _(
                        "El expediente está cerrado como «%s»; no puede avanzar de etapa. "
                        "Solo puede cancelarse si corresponde."
                    )
                    % rec.stage_id.name
                )
            if not self.env.context.get("skip_document_check"):
                rec._check_required_documents_before_leave_stage()
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
            rec._check_spend_request_before_leave_stage()
            # En la primera etapa exigimos que el expediente tenga un monto
            # estimado mayor a cero (cargado manualmente o por suma de líneas)
            # antes de pasar a la siguiente. Sin monto no tiene sentido avanzar
            # con la solicitud de aprobación / cotizaciones.
            if current_index == 0 and not (rec.amount_estimated and rec.amount_estimated > 0):
                raise UserError(
                    _(
                        "Debe cargar un monto estimado mayor a cero antes de "
                        "pasar de la primera etapa. Cárguelo manualmente en "
                        "«Total estimado» o detallándolo en las líneas."
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

    def action_link_child_expedient(self):
        """Vincula como hijo el expediente elegido en `child_picker_id`.

        Esta acción evita que al "Agregar línea" en el One2many de
        expedientes relacionados se cree un expediente nuevo: el usuario
        elige uno existente desde el selector y se asocia mediante
        `parent_id`.
        """
        self.ensure_one()
        picker = self.child_picker_id
        if not picker:
            raise UserError(_("Seleccione un expediente para vincular."))
        if picker.id == self.id:
            raise UserError(_("No puede vincularse un expediente consigo mismo."))
        if picker.parent_id and picker.parent_id.id != self.id:
            raise UserError(
                _(
                    "El expediente %s ya está vinculado como hijo del expediente %s."
                )
                % (picker.display_name, picker.parent_id.display_name)
            )
        if picker.id in self.child_ids.ids:
            raise UserError(_("El expediente seleccionado ya figura como relacionado."))
        picker.write({"parent_id": self.id})
        self.child_picker_id = False
        return True

    def action_unlink_child_expedient(self):
        """Quita el vínculo padre-hijo desde una fila del One2many `child_ids`.

        Pensado para invocarse con `self` siendo el hijo a desvincular
        (botón dentro de la lista).
        """
        for rec in self:
            rec.parent_id = False
        return True

    def action_previous_stage(self):
        for rec in self:
            if not rec.can_edit_in_stage:
                raise UserError(
                    _(
                        "Solo los usuarios asignados a la etapa actual pueden volver a la etapa anterior."
                    )
                )
            if not self.env.context.get("skip_document_check"):
                rec._check_required_documents_before_leave_stage()
        for rec, stages in self._get_allowed_stages():
            if not rec.stage_id or not stages:
                continue
            current_index = stages.ids.index(rec.stage_id.id) if rec.stage_id.id in stages.ids else -1
            if current_index <= 0:
                continue
            target = stages[current_index - 1]
            rec.stage_id = target
        return True

    @api.depends_context("uid")
    def _compute_payment_ids(self):
        Payment = self.env["account.payment"]
        for rec in self:
            if not rec._user_can_read_account_payments():
                rec.payment_ids = Payment
                rec.payment_count = 0
                continue
            payments_direct = Payment.search([("expedient_ids", "in", rec.ids)])
            invoices = rec._invoices_data()
            payments_via_invoice = invoices.mapped("reconciled_payment_ids")
            all_payments = payments_direct | payments_via_invoice
            rec.payment_ids = all_payments
            rec.payment_count = len(all_payments)

    def _invoices_data(self):
        """Facturas reales para cómputos y smart buttons.

        - Gasto: facturas de proveedor (in_invoice/in_refund) desde OC + directas.
        - Ingreso: facturas de venta (out_invoice/out_refund) vinculadas.

        Se filtra explícitamente por `move_type` porque las facturas de gasto e
        ingreso comparten la tabla de relación (`fund_expedient_account_move_rel`).
        """
        self.ensure_one()
        linked = self._direct_invoices_data()
        if self.operation_type == "income":
            return linked.filtered(lambda m: m.move_type in ("out_invoice", "out_refund"))
        invoices_po = self._purchase_orders_data().mapped("invoice_ids")
        purchase_direct = linked.filtered(lambda m: m.move_type in ("in_invoice", "in_refund"))
        return invoices_po | purchase_direct

    @api.depends_context("uid")
    def _compute_invoice_ids(self):
        for rec in self:
            if not rec._user_can_read_account_moves():
                rec.invoice_ids = self.env["account.move"]
                rec.invoice_count = 0
                continue
            all_invoices = rec._invoices_data()
            rec.invoice_ids = all_invoices
            rec.invoice_count = len(all_invoices)

    @api.depends(
        "amount_estimated",
        "amount_estimated_confirmed",
        "request_date",
        "company_id",
        "currency_id",
        "approval_currency_id",
        "operation_type",
        "stage_id",
        "type_id.stage_assign_ids.committed_from_expedient",
    )
    @api.depends_context("uid")
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

            # Comprometido: si la etapa lo toma del expediente, se convierte el
            # definitivo (misma regla que `_compute_amounts`); si no, se recorren
            # las OC igual que siempre, convirtiendo a moneda del tipo.
            if rec._committed_from_expedient():
                if rec.amount_estimated_confirmed and rec.request_date:
                    rec.amount_committed_unit = company_currency._convert(
                        rec.amount_estimated_confirmed, unit_currency, company, rec.request_date
                    )
                else:
                    rec.amount_committed_unit = 0.0
            else:
                pos_committed = rec._purchase_orders_data().filtered(
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

            # Real: facturas posteadas convertidas a moneda del tipo por fecha de factura.
            # Signo según operación (ver _compute_amounts): ingreso +, gasto −.
            real_sign = 1.0 if rec.operation_type == "income" else -1.0
            all_invoices = rec._invoices_data().filtered(lambda m: m.state == "posted")
            real_unit = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                signed = real_sign * inv.amount_total_signed
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

    def _committed_from_expedient(self):
        """True si la etapa actual toma el comprometido del propio expediente.

        Se configura por etapa en el tipo de expediente
        (`fund.expedient.type.stage.assign.committed_from_expedient`) y sirve para
        los circuitos sin solicitudes de cotización: el compromiso sale de los
        importes definitivos cargados en el expediente en lugar de las OC.
        """
        self.ensure_one()
        assign = self._current_stage_assign()
        return bool(assign and assign.committed_from_expedient)

    @api.depends(
        "company_id",
        "operation_type",
        "amount_estimated_confirmed",
        "stage_id",
        "type_id.stage_assign_ids.committed_from_expedient",
    )
    @api.depends_context("uid")
    def _compute_amounts(self):
        for rec in self:
            company_currency = rec.company_id.currency_id

            if rec._committed_from_expedient():
                # Etapa sin cotizaciones: el compromiso es el importe definitivo
                # del expediente (suma de líneas o total confirmado manual), ya
                # expresado en moneda compañía. Reemplaza al de las OC para no
                # contar dos veces el mismo compromiso.
                rec.amount_committed = rec.amount_estimated_confirmed or 0.0
            else:
                # Total Comprometido: OC confirmadas menos facturado (posteado).
                # Nota: con "facturación al recibir", qty_to_invoice puede ser 0 hasta recibir, pero el
                # compromiso debería reflejar el total ordenado desde la confirmación.
                pos_committed = rec._purchase_orders_data().filtered(
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

            # Total Real: facturas posteadas.
            #  - Gasto: facturas de proveedor (amount_total_signed negativo) → magnitud positiva con -signed.
            #  - Ingreso: facturas de venta (amount_total_signed positivo) → magnitud positiva con +signed.
            real_sign = 1.0 if rec.operation_type == "income" else -1.0
            all_invoices = rec._invoices_data().filtered(lambda m: m.state == "posted")
            amount_real = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                signed = real_sign * inv.amount_total_signed
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
            res = super().write(vals)
            if "description" in vals:
                self._apply_dynamic_placeholders_to_description()
            return res

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
            if (
                "type_id" in new_vals
                and new_vals.get("type_id")
                and new_vals.get("type_id") != rec.type_id.id
                and not self.env.context.get("skip_type_change_check")
            ):
                assign_cur = Assign.search(
                    [
                        ("type_id", "=", rec.type_id.id),
                        ("stage_id", "=", rec.stage_id.id),
                    ],
                    limit=1,
                )
                if assign_cur and not assign_cur.allow_edit_type_id:
                    raise UserError(
                        _(
                            "No puede cambiar el tipo de expediente en la etapa «%s». "
                            "Habilite «Permitir modificar tipo» en la configuración del tipo para esta etapa."
                        )
                        % rec.stage_id.name
                    )

            # Regenerar el "Número por tipo" cuando cambia el tipo:
            # cada tipo mantiene su propia secuencia, por lo que el número anterior
            # ya no corresponde. Si el nuevo tipo no tiene secuencia, limpiamos el campo.
            if (
                "type_id" in new_vals
                and new_vals.get("type_id")
                and new_vals.get("type_id") != rec.type_id.id
                and "type_number" not in new_vals
            ):
                new_type = Type.browse(new_vals["type_id"])
                if new_type.sequence_id:
                    new_vals["type_number"] = (
                        new_type.sequence_id.next_by_id() or False
                    )
                else:
                    new_vals["type_number"] = False

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

            stage_will_change = (
                "stage_id" in new_vals
                and new_vals.get("stage_id")
                and new_vals.get("stage_id") != rec.stage_id.id
            )

            if (
                "amount_estimated_confirmed_manual" in new_vals
                and not rec.line_amount_final_editable
                and not self.env.context.get("skip_final_amount_check")
            ):
                raise UserError(
                    _(
                        "No puede modificar el importe definitivo confirmado en la etapa «%s»."
                    )
                    % (rec.stage_id.name or "")
                )

            if (
                stage_will_change
                and rec.stage_id
                and not self.env.context.get("skip_spend_request_check")
                and rec._stage_change_is_forward(new_vals.get("stage_id"))
            ):
                rec._check_spend_request_before_leave_stage()

            if (
                stage_will_change
                and rec.type_id
                and rec.stage_id
                and not self.env.context.get("skip_document_check")
            ):
                rec._check_required_documents_before_leave_stage()

            # Reglas de disposición: al salir de la etapa actual, validar requisitos configurados.
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
            if "description" in new_vals:
                rec._apply_dynamic_placeholders_to_description()
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
            if vals.get("type_id") and not vals.get("type_number"):
                expedient_type = Type.browse(vals["type_id"])
                if expedient_type.sequence_id:
                    vals["type_number"] = expedient_type.sequence_id.next_by_id() or False
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
        records = super().create(vals_list)
        # Resolver placeholders dinámicos ({{ object.campo }}) ahora que el
        # expediente ya tiene id y valores persistidos.
        records._apply_dynamic_placeholders_to_description()
        return records

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

    @api.model
    def _html_has_dynamic_placeholders(self, value):
        """True si el texto contiene placeholders dinámicos.

        El selector del editor html inserta nodos qweb ``<t t-out="object.campo">``;
        también admitimos la sintaxis inline ``{{ object.campo }}`` por si se tipea
        a mano. Detectamos ambos para decidir si hay que renderizar.
        """
        if not value:
            return False
        text = str(value).lower()
        if "{{" in text and "}}" in text:
            return True
        return any(d in text for d in ("t-out", "t-esc", "t-field", "t-if", "t-foreach"))

    def _render_dynamic_template_value(self, template_src):
        """Renderiza placeholders dinámicos contra este expediente.

        Usa el motor 'qweb' de mail.render.mixin, donde 'object' es el propio
        expediente (los nodos ``<t t-out="object.campo">`` que inserta el editor
        son qweb). Devuelve el texto original si algo falla, para nunca bloquear la
        creación/edición por un placeholder mal escrito.
        """
        self.ensure_one()
        if not template_src:
            return template_src
        try:
            return self.env["mail.render.mixin"]._render_template(
                template_src,
                self._name,
                self.ids,
                engine="qweb",
            )[self.id]
        except Exception as e:
            _logger.warning(
                "No se pudieron renderizar placeholders dinámicos en el expediente "
                "%s (id=%s): %s",
                self.display_name,
                self.id,
                e,
            )
            return template_src

    def _apply_dynamic_placeholders_to_description(self):
        """Resuelve los placeholders dinámicos de Descripción/Memo en cada expediente.

        Se llama después de create/write (cuando el registro ya tiene id y valores
        persistidos). Escribe vía super().write para no reentrar en las validaciones
        de etapa ni en este mismo post-proceso.
        """
        for rec in self:
            if not self._html_has_dynamic_placeholders(rec.description):
                continue
            rendered = rec._render_dynamic_template_value(rec.description)
            if rendered and rendered != rec.description:
                super(FundExpedient, rec).write({"description": rendered})

    def _get_spend_request(self, create_if_missing=False):
        self.ensure_one()
        sr = self.spend_request_ids[:1]
        if sr:
            return sr
        if create_if_missing:
            return self.env["fund.expedient.spend.request"].create({"expedient_id": self.id})
        raise UserError(
            _("No existe Solicitud de Gasto para este expediente. Genérela desde la etapa correspondiente.")
        )

    def _missing_required_document_types(self):
        """Tipos de documento exigidos por la etapa actual que aún no se subieron.

        Un tipo se considera cumplido si existe un documento de ese tipo, con
        archivo cargado y cuya etapa origen es la etapa actual del expediente
        (los documentos de etapas anteriores no cuentan).
        """
        self.ensure_one()
        assign = self._current_stage_assign()
        if not assign or not assign.required_document_type_ids:
            return self.env["fund.expedient.document.type"]
        stage_docs = self.document_ids.filtered(
            lambda doc: doc.stage_id == self.stage_id and doc.file_data
        )
        uploaded_types = stage_docs.mapped("document_type_id")
        return assign.required_document_type_ids - uploaded_types

    def _check_required_documents_before_leave_stage(self):
        """Valida los tipos de documento obligatorios configurados en la etapa."""
        self.ensure_one()
        missing = self._missing_required_document_types()
        if missing:
            # Un solo error con todos los faltantes: evita que el usuario tenga
            # que reintentar el avance una vez por cada documento que falta.
            raise UserError(
                _(
                    "Para salir de la etapa «%(stage)s» debe adjuntar en esta etapa un "
                    "documento con archivo de cada uno de estos tipos: %(types)s.",
                    stage=self.stage_id.name or "",
                    types=", ".join(missing.mapped("name")),
                )
            )

    def _check_spend_request_before_leave_stage(self):
        """Valida SG al salir de etapa preventiva o definitiva."""
        self.ensure_one()
        mode = self.stage_id.spend_request_mode
        if mode not in ("preventiva", "final"):
            return
        sr = self.spend_request_ids[:1]
        if not sr:
            raise UserError(
                _("Debe generar la Solicitud de Gasto antes de salir de la etapa «%s».")
                % self.stage_id.name
            )
        if mode == "preventiva":
            if not sr.is_phase_generated("preventiva"):
                raise UserError(
                    _("Debe generar la Solicitud de Gasto preventiva antes de salir de esta etapa.")
                )
            if not sr.is_phase_approved("preventiva"):
                raise UserError(
                    _("La Solicitud de Gasto preventiva debe estar aprobada antes de salir de esta etapa.")
                )
        if mode == "final":
            if not sr.is_phase_generated("definitiva"):
                raise UserError(
                    _("Debe generar la Solicitud de Gasto definitiva antes de salir de esta etapa.")
                )
            if not sr.is_phase_approved("definitiva"):
                raise UserError(
                    _("La Solicitud de Gasto definitiva debe estar aprobada antes de salir de esta etapa.")
                )

    def action_create_spend_request_initial(self):
        self.ensure_one()
        if not self.stage_id or self.stage_id.spend_request_mode != "preventiva":
            raise UserError("La etapa actual no permite crear Solicitud de Gasto preventiva.")
        if self.spend_request_ids:
            raise UserError(_("Ya existe una Solicitud de Gasto para este expediente."))
        sr = self._get_spend_request(create_if_missing=True)
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
        sr = self._get_spend_request()
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

    def _find_outcome_stage(self, outcome):
        """Etapa final del flujo para un resultado (desierto/sin_efecto/fracasado).

        Si el tipo define asignaciones por etapa, la etapa debe estar en el flujo
        del tipo (igual criterio que el resto de las etapas). Sin tipo/asignaciones,
        se busca globalmente por compañía.
        """
        self.ensure_one()
        if self.type_id and self.type_id.stage_assign_ids:
            stages = (
                self.type_id.stage_assign_ids.mapped("stage_id")
                .filtered(lambda s: s.final_outcome == outcome)
                .sorted(key=lambda s: (s.sequence, s.id))
            )
            return stages[:1]
        return self.env["fund.expedient.stage"].search(
            [
                ("final_outcome", "=", outcome),
                ("company_id", "in", [False, self.company_id.id]),
            ],
            order="sequence, id",
            limit=1,
        )

    def _apply_disposition_outcome(self, outcome, disposition=None):
        """Cierra el expediente en la etapa final del resultado indicado.

        Se invoca desde la Disposición (botón «Aplicar disposición»). El salto
        omite las validaciones de salida de etapa (SG, documentos, disposición,
        resolución, notificación y tier): declarar desierto/sin efecto/fracasado
        es un cierre administrativo, análogo a Cancelar. El permiso de etapa
        (usuarios asignados) sí se exige.
        """
        self.ensure_one()
        if not self.can_edit_in_stage:
            raise UserError(
                _(
                    "Solo los usuarios asignados a la etapa actual pueden aplicar "
                    "la disposición y cerrar el expediente."
                )
            )
        target = self._find_outcome_stage(outcome)
        if not target:
            raise UserError(
                _(
                    "No hay una etapa final configurada para el resultado «%s». "
                    "Cree una etapa con ese Resultado final y agréguela a las "
                    "Asignaciones por etapa del tipo de expediente."
                )
                % dict(
                    self.env["fund.expedient.stage"]._fields["final_outcome"].selection
                ).get(outcome, outcome)
            )
        if self.stage_id == target:
            return True
        old_stage = self.stage_id
        self.with_context(
            skip_validation_check=True,
            skip_spend_request_check=True,
            skip_document_check=True,
            skip_disposition_check=True,
            skip_resolution_check=True,
            skip_notification_check=True,
        ).write({"stage_id": target.id})
        self.message_post(
            body=_(
                "El expediente pasó de la etapa <b>%(old)s</b> a <b>%(new)s</b> "
                "por aplicación de la disposición %(disp)s.",
                old=old_stage.name or "",
                new=target.name,
                disp=disposition.name if disposition else "",
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_view_purchase_orders(self):
        self.ensure_one()
        if not self._user_can_read_purchase_orders():
            raise UserError(
                _("No tiene permisos de Compras para ver las solicitudes de cotización.")
            )
        action = {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de cotización",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self._purchase_orders_data().ids)],
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
        if not self._user_can_read_account_moves():
            raise UserError(_("No tiene permisos de Contabilidad para ver las facturas."))
        default_move_type = (
            "out_invoice" if self.operation_type == "income" else "in_invoice"
        )
        name = "Facturas de venta" if self.operation_type == "income" else "Facturas"
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {
                "default_expedient_ids": [(4, self.id)],
                "default_move_type": default_move_type,
            },
        }

    def action_wizard_create_purchase(self):
        self.ensure_one()
        if not self._user_can_read_purchase_orders():
            raise UserError(
                _("No tiene permisos de Compras para crear solicitudes de cotización.")
            )
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
        if not self._user_can_read_account_payments():
            raise UserError(_("No tiene permisos de Contabilidad para ver los pagos."))
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

    # ------------------------------------------------------------------
    # Responsable actual del expediente
    #
    # `_get_pending_approval_info` y `_search_ids_with_pending_approval` son
    # puntos de extensión: el módulo base no conoce las tier reviews, así que
    # devuelven "sin aprobaciones pendientes". `expedient_tier_validation` los
    # sobreescribe para mirar las reviews del expediente y de su Solicitud.
    # ------------------------------------------------------------------

    def _get_pending_approval_info(self):
        """Aprobaciones pendientes del expediente.

        Devuelve la tupla ``(users, reason, label)``:
        - ``users``: recordset de ``res.users`` que deben aprobar ahora.
        - ``reason``: valor de ``holder_reason`` (``expedient_approval`` o
          ``spend_request_approval``), o False si no hay nada pendiente.
        - ``label``: texto de contexto para el cartel (p. ej. la etapa o la fase).
        """
        self.ensure_one()
        return self.env["res.users"], False, ""

    @api.model
    def _search_ids_with_pending_approval(self, user):
        """Ids de expedientes con aprobaciones pendientes.

        Devuelve ``(ids_con_pendientes, ids_pendientes_de_user)``: el primer
        conjunto sirve para excluir del filtro "En mi poder" a los asignados de
        etapa cuando el expediente está esperando una aprobación; el segundo,
        para el filtro "Esperando mi aprobación".
        """
        return set(), set()

    def _holder_names_text(self, users, limit=6):
        """Nombres de los responsables, truncados para no romper el cartel."""
        names = users.mapped("name")
        if len(names) > limit:
            return _(
                "%(names)s y %(extra)s más",
                names=", ".join(names[:limit]),
                extra=len(names) - limit,
            )
        return ", ".join(names)

    @api.depends(
        "stage_id",
        "assignable_user_ids",
    )
    def _compute_holder(self):
        for rec in self:
            users, reason, label = rec._get_pending_approval_info()
            if users and reason:
                # `label` describe qué se está aprobando (la etapa o la fase de
                # la solicitud); lo aporta el módulo de tier validation.
                rec.holder_user_ids = [(6, 0, users.ids)]
                rec.holder_reason = reason
                rec.holder_summary = _(
                    "Esperando aprobación de %(what)s: %(users)s",
                    what=label or _("este expediente"),
                    users=rec._holder_names_text(users),
                )
                continue

            # `assignable_user_ids` ya está almacenado y se calcula con
            # `_get_assignable_user_ids()`: usarlo evita un search por registro
            # (importante en kanban/lista, que computan por lote).
            stage_users = rec.assignable_user_ids if rec.stage_id else rec.env["res.users"]
            if stage_users:
                rec.holder_user_ids = [(6, 0, stage_users.ids)]
                rec.holder_reason = "stage"
                rec.holder_summary = _(
                    "En la etapa «%(stage)s» el expediente está en manos de: %(users)s",
                    stage=rec.stage_id.name or "",
                    users=rec._holder_names_text(stage_users),
                )
            else:
                # Sin asignación configurada para la etapa: cualquiera con
                # permisos puede operar, así que no afirmamos un responsable.
                rec.holder_user_ids = [(6, 0, [])]
                rec.holder_reason = False
                rec.holder_summary = ""

    def _search_holder_user_ids(self, operator, value):
        """Buscar por responsable actual (no se puede sobre un compute sin store).

        Se resuelve a ids: quienes esperan aprobación del usuario, más los
        expedientes asignados a él por etapa que NO estén esperando aprobación
        (en ese caso el responsable son los aprobadores, no el asignado).
        """
        if operator not in ("in", "not in", "=", "!=") or not value:
            raise UserError(
                _("La búsqueda por «En poder de» solo admite igualdad sobre usuarios.")
            )
        user_ids = value if isinstance(value, (list, tuple)) else [value]
        users = self.env["res.users"].browse(user_ids)
        pending_all, pending_mine = self._search_ids_with_pending_approval(users)
        assigned = self.search([("assignable_user_ids", "in", users.ids)])
        holder_ids = set(pending_mine) | (set(assigned.ids) - set(pending_all))
        negative = operator in ("not in", "!=")
        return [("id", "not in" if negative else "in", list(holder_ids))]
