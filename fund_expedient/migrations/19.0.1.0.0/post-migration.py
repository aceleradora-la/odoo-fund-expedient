# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Odoo 19: grupos de Expedientes colgados de su privilegio.

En Odoo 19 los grupos no tienen categoría: la tienen los privilegios
(res.groups.privilege). Usuario y Administrador se declaran en un bloque
noupdate, así que el upgrade no les asigna el privilegio nuevo; se hace acá.
Solo se completa si el grupo no tiene privilegio (la plataforma de upgrade
de Odoo pudo haber asignado uno al convertir las categorías).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_GROUP_PRIVILEGES = {
    "fund_expedient.group_fund_expedient_user": "fund_expedient.privilege_fund_expedient",
    "fund_expedient.group_fund_expedient_manager": "fund_expedient.privilege_fund_expedient",
    "fund_expedient.group_fund_expedient_contracting": (
        "fund_expedient.privilege_fund_expedient_contracting"
    ),
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for group_xmlid, privilege_xmlid in _GROUP_PRIVILEGES.items():
        group = env.ref(group_xmlid, raise_if_not_found=False)
        privilege = env.ref(privilege_xmlid, raise_if_not_found=False)
        if not group or not privilege:
            _logger.warning("Migración 19.0: falta %s o %s", group_xmlid, privilege_xmlid)
            continue
        if not group.privilege_id:
            group.privilege_id = privilege
