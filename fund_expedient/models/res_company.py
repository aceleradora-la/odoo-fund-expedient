# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

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
