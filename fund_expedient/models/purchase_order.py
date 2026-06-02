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

    def _touch_linked_expedient_commercial_fields(self):
        self.mapped("expedient_ids")._invalidate_commercial_computes()

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._touch_linked_expedient_commercial_fields()
        return orders

    def write(self, vals):
        before = self.mapped("expedient_ids")
        res = super().write(vals)
        (before | self.mapped("expedient_ids"))._invalidate_commercial_computes()
        return res

    def unlink(self):
        expedients = self.mapped("expedient_ids")
        res = super().unlink()
        expedients._invalidate_commercial_computes()
        return res

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
