# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    # Compatibilidad: mantenemos el campo legacy (Many2one) y migramos a multi-proveedor.
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

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_po_id or self.product_id.uom_id

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
