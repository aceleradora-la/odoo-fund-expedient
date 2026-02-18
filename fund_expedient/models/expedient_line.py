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
    recommended_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor recomendado",
        domain=[("is_company", "=", True)],
        help="Si está vacío, se usa el proveedor recomendado del expediente.",
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
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
