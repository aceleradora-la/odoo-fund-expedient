# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ExpedientConfig(models.Model):
    _name = "fund.expedient.config"
    _description = "Configuración de Expedientes"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    expedient_service_product_id = fields.Many2one(
        "product.product",
        string="Producto servicio para líneas sin producto",
        domain=[
            ("type", "=", "service"),
            ("purchase_ok", "=", True),
        ],
        help="Producto de tipo servicio usado cuando una línea del expediente "
        "solo tiene descripción (sin producto). Se crea una OC con este producto.",
    )

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Solo puede haber una configuración por compañía.",
        )
    ]

    @api.model
    def get_service_product(self, company):
        """Obtener el producto servicio para la compañía."""
        config = self.search([("company_id", "=", company.id)], limit=1)
        return config.expedient_service_product_id
