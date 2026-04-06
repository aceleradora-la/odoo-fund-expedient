# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)


class FundExpedient(models.Model):
    _name = "fund.expedient"
    _description = "Expediente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "number"
    _rec_names_search = ["number", "description"]

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
    recommended_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor recomendado",
        tracking=True,
        domain=[("is_company", "=", True)],
    )
    requestor_id = fields.Many2one(
        "hr.employee",
        string="Solicitante",
        required=True,
        default=lambda self: self._default_requestor_id(),
        tracking=True,
    )
    type_unit_mode = fields.Selection(
        related="type_id.unit_mode",
        string="Unidad de aprobación (tipo)",
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
    hide_budget_position_id_stage = fields.Boolean(
        string="Ocultar Partida presupuestaria por etapa",
        compute="_compute_stage_field_visibility",
    )
    hide_amount_estimated_stage = fields.Boolean(
        string="Ocultar Total estimado por etapa",
        compute="_compute_stage_field_visibility",
    )
    budget_position_id = fields.Many2one(
        "fund.budget.position",
        string="Partida presupuestaria asignada",
        tracking=True,
        domain="[('budget_assignment_allowed', '=', True)]",
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
    description = fields.Text(
        string="Descripción/Memo",
        tracking=True,
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
    amount_estimated = fields.Monetary(
        string="Total Estimado",
        currency_field="currency_id",
        tracking=True,
    )
    amount_estimated_uf = fields.Float(
        string="Total Estimado (UR)",
        compute="_compute_amount_estimated_uf",
        store=True,
        digits=(16, 4),
    )
    amount_committed = fields.Monetary(
        string="Total Comprometido",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_committed_uf = fields.Float(
        string="Total Comprometido (UR)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
    )
    amount_real = fields.Monetary(
        string="Total Real",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_real_uf = fields.Float(
        string="Total Real (UR)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
    )
    amount_estimated_ufunc = fields.Float(
        string="Total Estimado (UF)",
        compute="_compute_amount_estimated_ufunc",
        store=True,
        digits=(16, 4),
    )
    amount_committed_ufunc = fields.Float(
        string="Total Comprometido (UF)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
    )
    amount_real_ufunc = fields.Float(
        string="Total Real (UF)",
        compute="_compute_amounts",
        store=True,
        digits=(16, 4),
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
            rec.hide_budget_position_id_stage = False
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
            rec.hide_budget_position_id_stage = assign.hide_budget_position_id
            rec.hide_amount_estimated_stage = assign.hide_amount_estimated

    @api.depends("type_id", "type_id.stage_assign_ids", "company_id")
    def _compute_allowed_stage_ids(self):
        Stage = self.env["fund.expedient.stage"]
        for rec in self:
            if rec.type_id and rec.type_id.stage_assign_ids:
                rec.allowed_stage_ids = rec.type_id.stage_assign_ids.mapped("stage_id").sorted(
                    key=lambda s: (s.sequence, s.id)
                )
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

    @api.depends("amount_estimated", "request_date", "company_id")
    def _compute_amount_estimated_uf(self):
        UfRate = self.env["fund.uf.rate"]
        for rec in self:
            if not rec.amount_estimated or not rec.request_date:
                rec.amount_estimated_uf = 0.0
                continue
            rate_ur = UfRate.get_rate(rec.company_id, rec.request_date, unit_type="ur")
            rec.amount_estimated_uf = rate_ur and (rec.amount_estimated / rate_ur) or 0.0

    @api.depends("amount_estimated", "request_date", "company_id")
    def _compute_amount_estimated_ufunc(self):
        UfRate = self.env["fund.uf.rate"]
        for rec in self:
            if not rec.amount_estimated or not rec.request_date:
                rec.amount_estimated_ufunc = 0.0
                continue
            rate_uf = UfRate.get_rate(rec.company_id, rec.request_date, unit_type="uf")
            rec.amount_estimated_ufunc = rate_uf and (rec.amount_estimated / rate_uf) or 0.0

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
        UfRate = self.env["fund.uf.rate"]
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

            # Totales comprometidos en UR y UF
            committed_ur = 0.0
            committed_ufunc = 0.0
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
                amt_cc = max(0.0, ordered_cc - invoiced_cc)

                rate_ur = UfRate.get_rate(rec.company_id, po_date, unit_type="ur")
                if rate_ur:
                    committed_ur += amt_cc / rate_ur
                rate_uf = UfRate.get_rate(rec.company_id, po_date, unit_type="uf")
                if rate_uf:
                    committed_ufunc += amt_cc / rate_uf
            rec.amount_committed_uf = committed_ur
            rec.amount_committed_ufunc = committed_ufunc

            # Total Real: facturas posteadas (desde OC o directas)
            invoices_po = rec.purchase_order_ids.mapped("invoice_ids").filtered(
                lambda m: m.state == "posted"
            )
            invoices_direct = rec.direct_invoice_ids.filtered(
                lambda m: m.state == "posted"
            )
            all_invoices = invoices_po | invoices_direct
            amount_real = 0.0
            amount_real_ur = 0.0
            amount_real_ufunc = 0.0
            for inv in all_invoices:
                inv_date = inv.invoice_date or inv.date
                # amount_total_signed: negativo para facturas, positivo para devoluciones
                signed = -inv.amount_total_signed
                amt_cc = inv.currency_id._convert(
                    signed, company_currency, rec.company_id, inv_date
                )
                amount_real += amt_cc
                rate_ur = UfRate.get_rate(rec.company_id, inv_date, unit_type="ur")
                if rate_ur:
                    amount_real_ur += amt_cc / rate_ur
                rate_uf = UfRate.get_rate(rec.company_id, inv_date, unit_type="uf")
                if rate_uf:
                    amount_real_ufunc += amt_cc / rate_uf
            rec.amount_real = amount_real
            rec.amount_real_uf = amount_real_ur
            rec.amount_real_ufunc = amount_real_ufunc

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

            stage_will_change = (
                "stage_id" in new_vals
                and new_vals.get("stage_id")
                and new_vals.get("stage_id") != rec.stage_id.id
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
