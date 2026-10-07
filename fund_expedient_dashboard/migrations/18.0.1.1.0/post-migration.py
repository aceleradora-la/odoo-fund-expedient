# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Un solo grupo «Expedientes» en Tableros.

Antes del módulo, el tablero de Expedientes se cargaba a mano subiendo el
JSON, en un grupo «Expedientes» creado también a mano. Al instalar el módulo
quedaban dos grupos con el mismo nombre. Se pasan los tableros de esos grupos
al del módulo y se borran los grupos, ya vacíos. No se borra ningún tablero:
el viejo queda junto al nuevo para que el usuario lo elimine cuando quiera.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ours = env.ref(
        "fund_expedient_dashboard.spreadsheet_dashboard_group_expedientes",
        raise_if_not_found=False,
    )
    if not ours:
        return
    Group = env["spreadsheet.dashboard.group"]
    duplicates = Group.browse()
    for lang in {"en_US", "es_AR", "es_419", "es_ES"}:
        duplicates |= Group.with_context(lang=lang).search(
            [("name", "=ilike", "expedientes"), ("id", "!=", ours.id)]
        )
    for group in duplicates:
        group.dashboard_ids.write({"dashboard_group_id": ours.id})
        group.unlink()
