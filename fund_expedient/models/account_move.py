# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_account_move_rel",
        "move_id",
        "expedient_id",
        string="Expedientes",
        copy=False,
        help="Para facturas directas (sin orden de compra). "
        "Si la factura viene de una OC, la relación se toma de la orden.",
    )

    @api.onchange("expedient_ids")
    def _onchange_expedient_ids_analytic(self):
        """Si todos los expedientes apuntan a la misma cuenta analítica,
        se sugiere para las líneas de factura sin distribución cargada."""
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            analytics = move.expedient_ids.mapped("analytic_account_id").filtered(lambda a: a)
            if len(analytics) == 1:
                analytic = analytics[0]
                for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                    if not line.analytic_distribution:
                        line.analytic_distribution = {str(analytic.id): 100.0}

    def write(self, vals):
        res = super().write(vals)
        if "expedient_ids" in vals:
            for move in self:
                if move.move_type in ("in_invoice", "in_refund") and move.expedient_ids:
                    analytics = move.expedient_ids.mapped("analytic_account_id").filtered(lambda a: a)
                    if len(analytics) == 1:
                        analytic = analytics[0]
                        lines_to_update = move.invoice_line_ids.filtered(
                            lambda l: not l.display_type and not l.analytic_distribution
                        )
                        if lines_to_update:
                            lines_to_update.write({"analytic_distribution": {str(analytic.id): 100.0}})
        if any(
            f in vals
            for f in ("expedient_ids", "state", "amount_total", "currency_id", "invoice_line_ids")
        ):
            # Recompute de importes comprometidos/reales del expediente
            # cuando cambia la factura o su vínculo.
            expedients = self.mapped("expedient_ids")
            for move in self:
                if move.move_type in ("in_invoice", "in_refund"):
                    pos = move.invoice_line_ids.purchase_line_id.order_id
                    for po in pos:
                        if po.expedient_ids:
                            expedients |= po.expedient_ids
            if expedients:
                expedients._invalidate_commercial_computes()
        return res
