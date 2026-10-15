# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Privacidad para todos los expedientes: participantes como seguidores.

Desde esta versión todo expediente (no solo las Locaciones) lo ven solo sus
participantes y los Administradores, y los participantes quedan como
seguidores. Los participantes ya se cargaron del historial (18.0.18.0); acá
se los suscribe, pero solo en los expedientes abiertos: suscribir a todos en
los cerrados solo generaría avisos de expedientes que ya no se mueven. El
acceso a los cerrados no depende de seguirlos.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    expedients = env["fund.expedient"].with_context(active_test=False).search(
        [("state", "not in", ("done", "no_award", "cancel"))]
    )
    for expedient in expedients:
        partners = expedient.participant_user_ids.partner_id
        if partners:
            expedient.message_subscribe(partner_ids=partners.ids)
