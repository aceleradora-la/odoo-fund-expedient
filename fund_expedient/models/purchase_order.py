# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_purchase_order_rel",
        "order_id",
        "expedient_id",
        string="Expedientes",
        tracking=True,
        domain="[('stage_id.state_type', '=', 'purchases')]",
        help="Solo se pueden asociar expedientes que estén en etapa de tipo Compras.",
    )

    @api.constrains("expedient_ids")
    def _check_expedient_ids_stage_purchases(self):
        for order in self:
            bad = order.expedient_ids.filtered(
                lambda e: not e.stage_id or e.stage_id.state_type != "purchases"
            )
            if bad:
                raise ValidationError(
                    "Solo se pueden asociar expedientes que estén en la etapa de tipo Compras. "
                    "Expedientes no válidos: %s."
                    % ", ".join(bad.mapped("number"))
                )
