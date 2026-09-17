# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Facturas de OC sin vínculo directo, y totales congelados.

- Las facturas generadas desde una OC no tenían `expedient_ids`: se completa
  desde la orden, como hace ahora `account.move` al crearlas.
- Comprometido y real se «invalidaban» con `modified()`, que no recalcula el
  campo mismo: los totales almacenados podían estar en cero aunque hubiera
  facturas publicadas. Se recalculan todos.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.fund_expedient.hooks import _recompute_expedient_commercial_amounts


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    bills = env["account.move"].search(
        [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("invoice_line_ids.purchase_line_id", "!=", False),
        ]
    )
    bills._sync_expedients_from_purchase()
    _recompute_expedient_commercial_amounts(env)
