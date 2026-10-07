# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Participantes de los expedientes existentes, y comprometido sin doble conteo.

- Las Locaciones pasan a ser visibles solo para sus participantes. Se carga
  `participant_user_ids` de lo que ya pasó: creador, último en modificarlo,
  solicitante, responsable del sector, responsable y asignados actuales, y
  todo usuario interno que haya dejado algo en el historial (cambios de
  etapa, mensajes, notas). Así nadie pierde un expediente en el que ya
  trabajó.
- El comprometido tomado del expediente ahora descuenta lo facturado: se
  recalculan los totales.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.fund_expedient.hooks import _recompute_expedient_commercial_amounts


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        INSERT INTO fund_expedient_participant_rel (expedient_id, user_id)
        SELECT DISTINCT e.id, u.id
          FROM fund_expedient e
          JOIN res_users u ON u.id IN (e.create_uid, e.write_uid)
         WHERE u.share IS NOT TRUE AND u.id != %(root)s
        UNION
        SELECT DISTINCT m.res_id, u.id
          FROM mail_message m
          JOIN fund_expedient e ON e.id = m.res_id
          JOIN res_users u ON u.partner_id = m.author_id
         WHERE m.model = 'fund.expedient'
           AND u.share IS NOT TRUE AND u.id != %(root)s
        ON CONFLICT DO NOTHING
        """,
        {"root": SUPERUSER_ID},
    )
    env["fund.expedient"].with_context(active_test=False).search([])._record_participants()
    _recompute_expedient_commercial_amounts(env)
