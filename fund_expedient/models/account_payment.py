# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
