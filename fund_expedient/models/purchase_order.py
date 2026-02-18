# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_purchase_order_rel",
        "order_id",
        "expedient_id",
        string="Expedientes",
        tracking=True,
    )
