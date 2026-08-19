# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_account_payment_rel",
        "payment_id",
        "expedient_id",
        string="Expedientes",
        copy=False,
        help="Para pagos directos (sin factura). Si el pago es a una factura "
        "relacionada, la vinculación se toma de la factura.",
    )
    expedient_names = fields.Char(
        string="Expedientes",
        compute="_compute_expedient_names",
        help="Números de los expedientes vinculados, en texto. Permite verlos sin "
        "tener permisos sobre el módulo de Expedientes.",
    )

    @api.depends("expedient_ids")
    def _compute_expedient_names(self):
        """Igual que en la factura: se expone solo el número, con sudo acotado.

        Un pago contra facturas hereda el expediente de ellas —la vinculación
        directa del pago es solo para pagos sin factura—, así que se suman las
        facturas conciliadas. Los nombres de campo se consultan de forma
        defensiva para no atarse a una versión concreta de Contabilidad.
        """
        for payment in self:
            expedients = payment.sudo().expedient_ids
            for field_name in ("reconciled_invoice_ids", "reconciled_bill_ids"):
                if field_name not in payment._fields:
                    continue
                invoices = payment[field_name]
                for invoice in invoices.sudo():
                    expedients |= invoice._expedients_for_display()
            names = expedients.mapped("display_name")
            payment.expedient_names = ", ".join(name for name in names if name)
