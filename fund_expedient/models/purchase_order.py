# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        ondelete="set null",
        index=True,
        tracking=True,
    )
