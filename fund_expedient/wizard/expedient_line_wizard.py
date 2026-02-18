# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ExpedientLineWizard(models.TransientModel):
    _name = "fund.expedient.line.wizard"
    _description = "Crear solicitudes de cotización desde líneas"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        readonly=True,
    )
    line_ids = fields.Many2many(
        "fund.expedient.line",
        "fund_expedient_line_wizard_line_rel",
        "wizard_id",
        "line_id",
        string="Líneas a incluir",
        domain="[('expedient_id', '=', expedient_id), ('display_type', '=', False)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor (líneas sin proveedor)",
        domain=[("is_company", "=", True)],
        help="Proveedor para las líneas que no tienen proveedor recomendado.",
    )
    supplier_summary = fields.Char(
        compute="_compute_supplier_summary",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "expedient_id" in fields_list and self.env.context.get("active_model") == "fund.expedient":
            res["expedient_id"] = self.env.context.get("active_id")
        if "line_ids" in fields_list and res.get("expedient_id"):
            expedient = self.env["fund.expedient"].browse(res["expedient_id"])
            lines = expedient.line_ids.filtered(lambda l: not l.display_type)
            res["line_ids"] = [(6, 0, lines.ids)]
        return res

    @api.depends("line_ids", "line_ids.recommended_supplier_id", "expedient_id.recommended_supplier_id")
    def _compute_supplier_summary(self):
        for wiz in self:
            if not wiz.line_ids:
                wiz.supplier_summary = ""
                continue
            grouped = wiz._group_lines_by_supplier()
            parts = []
            for partner, lines in grouped.items():
                name = partner.name if partner else "(Sin proveedor - completar)"
                parts.append(f"{name}: {len(lines)} línea(s)")
            wiz.supplier_summary = " | ".join(parts) if parts else ""

    def _group_lines_by_supplier(self):
        """Agrupa líneas por proveedor efectivo."""
        grouped = defaultdict(list)
        for line in self.line_ids:
            partner = line.recommended_supplier_id or self.expedient_id.recommended_supplier_id
            grouped[partner].append(line)
        return grouped

    def _get_service_product(self):
        product = self.expedient_id.company_id.expedient_service_product_id
        if not product:
            raise UserError(
                "Configure el producto servicio para líneas sin producto en "
                "Configuración > Compañía > Expedientes."
            )
        return product

    def _prepare_po_line(self, line):
        """Prepara valores para purchase.order.line."""
        if line.product_id:
            product = line.product_id
            name = line.name or product.display_name
        else:
            product = self._get_service_product()
            name = line.name or product.display_name
        return {
            "product_id": product.id,
            "name": name,
            "product_qty": line.product_qty,
            "product_uom_id": line.product_uom_id.id,
            "price_unit": 0.0,
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError("Seleccione al menos una línea.")
        if self.expedient_id.stage_id.state_type != "purchases":
            raise UserError(
                "Solo se pueden crear solicitudes de cotización cuando el expediente "
                "está en la etapa de Compras."
            )
        grouped = self._group_lines_by_supplier()
        if not grouped:
            raise ValidationError("No hay líneas seleccionadas.")
        PurchaseOrder = self.env["purchase.order"]
        created = self.env["purchase.order"]
        for partner, lines in grouped.items():
            if not partner:
                partner = self.partner_id
            if not partner:
                raise UserError(
                    "Hay líneas sin proveedor recomendado. Completar el proveedor "
                    "en las líneas, en el expediente, o seleccionar aquí."
                )
            po_vals = {
                "partner_id": partner.id,
                "expedient_ids": [(4, self.expedient_id.id)],
            }
            lines_vals = [self._prepare_po_line(ln) for ln in lines]
            po = PurchaseOrder.create(po_vals)
            for vals in lines_vals:
                vals["order_id"] = po.id
                self.env["purchase.order.line"].create(vals)
            created |= po
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitudes creadas",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }
