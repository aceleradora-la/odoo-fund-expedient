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
    amount_estimated_line = fields.Monetary(
        string="Importe estimado",
        currency_field="currency_id",
        default=0.0,
    )
    amount_final_line = fields.Monetary(
        string="Importe definitivo",
        currency_field="currency_id",
        default=0.0,
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
        if "amount_final_line" in vals and not self.env.context.get("skip_final_amount_check"):
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
