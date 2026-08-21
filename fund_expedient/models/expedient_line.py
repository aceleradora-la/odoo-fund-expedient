# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ExpedientLine(models.Model):
    _name = "fund.expedient.line"
    _description = "Línea de Expediente"
    _order = "expedient_id, sequence, id"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    display_type = fields.Selection(
        [("line_section", "Sección"), ("line_note", "Nota")],
        default=False,
        help="Tipo de línea para secciones o notas.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        domain=[("purchase_ok", "=", True)],
        ondelete="restrict",
    )
    name = fields.Char(
        string="Descripción",
        help="Descripción de la línea. Obligatoria si no hay producto. Con producto se completa automáticamente.",
    )
    product_qty = fields.Float(
        string="Cantidad",
        default=1.0,
        required=True,
        digits="Product Unit of Measure",
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad",
        required=True,
        default=lambda self: self._default_uom(),
    )
    recommended_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor recomendado (legacy)",
        domain=[("is_company", "=", True)],
        help="Campo legacy. Use 'Proveedores recomendados'.",
    )
    recommended_supplier_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="fund_expedient_line_recommended_supplier_rel",
        column1="line_id",
        column2="partner_id",
        string="Proveedores recomendados",
        domain=[("is_company", "=", True)],
        help="Lista de proveedores recomendados para esta línea. Si está vacío, se usarán los recomendados del expediente.",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        domain="[('plan_id', '=', analytic_plan_id), ('company_id', 'in', [False, company_id])]",
    )
    analytic_plan_id = fields.Many2one(
        "account.analytic.plan",
        compute="_compute_analytic_plan_id",
        store=False,
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )
    currency_id = fields.Many2one(
        related="expedient_id.currency_id",
        store=True,
        readonly=True,
    )
    contract_kind = fields.Selection(
        related="expedient_id.contract_kind",
        string="Locación",
        store=True,
        readonly=True,
    )
    # Precio unitario y total estimado: el precio unitario es el dato
    # cargado por el usuario; el total se calcula automáticamente como
    # `price_unit_estimated * product_qty`. Se mantiene `inverse` para
    # tolerar la edición directa del total (recalcula el unitario).
    price_unit_estimated = fields.Monetary(
        string="Precio unitario estimado",
        currency_field="currency_id",
        default=0.0,
        help="Precio unitario estimado de la línea. El total se calcula como unitario × cantidad.",
    )
    amount_estimated_line = fields.Monetary(
        string="Importe estimado",
        currency_field="currency_id",
        compute="_compute_amount_estimated_line",
        inverse="_inverse_amount_estimated_line",
        store=True,
        readonly=False,
        help="Total estimado de la línea = precio unitario × cantidad.",
    )
    price_unit_final = fields.Monetary(
        string="Precio unitario definitivo",
        currency_field="currency_id",
        default=0.0,
    )
    # Fechas de vigencia de la línea (solo para expedientes de locación de
    # servicios/obra). Se usan en el reporte de contratación y para prorratear
    # el importe en la proyección mensual de flujo de caja.
    date_start = fields.Date(string="Fecha inicio")
    date_end = fields.Date(string="Fecha fin")
    amount_final_line = fields.Monetary(
        string="Importe definitivo",
        currency_field="currency_id",
        compute="_compute_amount_final_line",
        inverse="_inverse_amount_final_line",
        store=True,
        readonly=False,
    )

    @api.depends("price_unit_estimated", "product_qty")
    def _compute_amount_estimated_line(self):
        for rec in self:
            # Solo recalcula si hay unitario cargado; si no, respetamos
            # cualquier valor que ya estuviera (compatibilidad con datos
            # previos a la introducción del precio unitario).
            if rec.price_unit_estimated:
                rec.amount_estimated_line = rec.price_unit_estimated * (rec.product_qty or 0.0)
            elif not rec.amount_estimated_line:
                rec.amount_estimated_line = 0.0

    def _inverse_amount_estimated_line(self):
        for rec in self:
            if rec.product_qty:
                rec.price_unit_estimated = rec.amount_estimated_line / rec.product_qty

    @api.depends("price_unit_final", "product_qty")
    def _compute_amount_final_line(self):
        for rec in self:
            if rec.price_unit_final:
                rec.amount_final_line = rec.price_unit_final * (rec.product_qty or 0.0)
            elif not rec.amount_final_line:
                rec.amount_final_line = 0.0

    def _inverse_amount_final_line(self):
        for rec in self:
            if rec.product_qty:
                rec.price_unit_final = rec.amount_final_line / rec.product_qty

    # Sector requirente y su responsable viven en el expediente (salen del
    # solicitante). Se traen almacenados para poder filtrarlos, agruparlos y
    # sumarlos en el reporte de contrataciones sin recorrer el expediente.
    requestor_department_id = fields.Many2one(
        "hr.department",
        string="Sector requirente",
        related="expedient_id.requestor_department_id",
        store=True,
        readonly=True,
        index=True,
    )
    requestor_department_manager_id = fields.Many2one(
        "hr.employee",
        string="Responsable del sector",
        related="expedient_id.requestor_department_manager_id",
        store=True,
        readonly=True,
        index=True,
    )

    # Campos auxiliares para el reporte de contratación (Locación). El proveedor
    # contratado y las facturas reales se vinculan a nivel expediente (no de
    # línea), por eso los traemos como computados desde el expediente.
    contracted_supplier_ids = fields.Many2many(
        "res.partner",
        string="Proveedor contratado",
        compute="_compute_contract_report_fields",
        help="Proveedores de las órdenes de compra vinculadas al expediente. Si el "
        "expediente no tiene orden de compra, se usan los proveedores cargados a "
        "mano: primero los de la línea y, si no hay, los generales del expediente "
        "(la misma precedencia que aplica el resto del módulo).",
    )
    expedient_amount_real = fields.Monetary(
        string="Facturas reales (expediente)",
        currency_field="currency_id",
        compute="_compute_contract_report_fields",
        help="Total real facturado del EXPEDIENTE completo (facturas de proveedor o de venta "
        "según la operación), no de esta línea: no existe imputación de facturas por línea. "
        "Por eso el mismo importe se repite en todas las líneas del expediente y no debe sumarse.",
    )

    @api.depends(
        "expedient_id.purchase_order_ids.partner_id",
        "expedient_id.amount_real",
        "recommended_supplier_ids",
        "expedient_id.recommended_supplier_ids",
    )
    def _compute_contract_report_fields(self):
        for rec in self:
            exp = rec.expedient_id
            if not exp:
                rec.contracted_supplier_ids = False
                rec.expedient_amount_real = 0.0
                continue
            # sudo: `purchase_order_ids` está restringido al grupo de compras;
            # este campo es informativo (reporte) y debe poder leerse aunque el
            # usuario no tenga permisos de Compras, sin romper la ficha.
            partners = exp.sudo().purchase_order_ids.mapped("partner_id")
            if not partners:
                # No toda contratación pasa por una orden de compra. Cuando no
                # hay, el proveedor es el que se cargó a mano en la línea y, si
                # la línea no define ninguno, el general del expediente.
                partners = rec.recommended_supplier_ids or exp.recommended_supplier_ids
            rec.contracted_supplier_ids = partners
            rec.expedient_amount_real = exp.amount_real

    @api.constrains("date_start", "date_end")
    def _check_contract_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(
                    _("La Fecha fin no puede ser anterior a la Fecha inicio en la línea del expediente.")
                )

    @api.model
    def _default_uom(self):
        return self.env.ref("uom.product_uom_unit", raise_if_not_found=False)

    @api.depends("expedient_id", "expedient_id.company_id")
    def _compute_analytic_plan_id(self):
        Config = self.env["fund.expedient.config"]
        for rec in self:
            plan = Config.get_analytic_plan(rec.expedient_id.company_id) if rec.expedient_id else False
            rec.analytic_plan_id = plan.id if plan else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exp = self.env["fund.expedient"].browse(vals.get("expedient_id")) if vals.get("expedient_id") else False
            if exp and not vals.get("analytic_account_id") and exp.analytic_account_id:
                vals["analytic_account_id"] = exp.analytic_account_id.id
        return super().create(vals_list)

    def write(self, vals):
        # `amount_final_line` queda como total y `price_unit_final` como
        # precio unitario; cualquiera de los dos al modificarse impacta
        # el importe definitivo, por lo que aplicamos la misma regla de
        # etapa en ambos.
        sensitive_keys = ("amount_final_line", "price_unit_final")
        if any(k in vals for k in sensitive_keys) and not self.env.context.get(
            "skip_final_amount_check"
        ):
            for rec in self:
                if not rec.expedient_id.line_amount_final_editable:
                    raise UserError(
                        _(
                            "No puede modificar el importe definitivo de la línea en la etapa «%s»."
                        )
                        % (rec.expedient_id.stage_id.name or "")
                    )
        return super().write(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_po_id or self.product_id.uom_id

    @api.onchange("expedient_id")
    def _onchange_expedient_id_defaults(self):
        if self.expedient_id and not self.analytic_account_id:
            self.analytic_account_id = self.expedient_id.analytic_account_id

    @api.constrains("product_id", "name", "display_type")
    def _check_name_required(self):
        for line in self:
            if (
                not line.display_type
                and not line.product_id
                and not (line.name and line.name.strip())
            ):
                raise ValidationError(
                    "La descripción es obligatoria cuando no hay producto."
                )
