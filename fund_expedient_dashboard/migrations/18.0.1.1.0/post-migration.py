# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Un solo grupo «Expedientes» en Tableros.

Antes del módulo, el tablero de Expedientes se cargaba a mano subiendo el
JSON, en un grupo «Expedientes» creado también a mano. Al instalar el módulo
quedaban dos grupos con el mismo nombre. Se pasan los tableros de esos grupos
al del módulo y se borran los grupos, ya vacíos. No se borra ningún tablero:
el viejo queda junto al nuevo para que el usuario lo elimine cuando quiera.

El nombre del grupo es traducible (jsonb con un valor por idioma): se busca
por SQL en cualquiera de sus traducciones. Buscar con el ORM cambiando el
idioma del contexto falla si el idioma no está instalado, y una migración que
falla tumba la actualización entera.

Los grupos que vienen de otro módulo no se tocan (Odoo no deja borrarlos y
ese módulo los volvería a crear): solo se avisa en el log.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


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
    cr.execute(
        """
        SELECT g.id
          FROM spreadsheet_dashboard_group g
         WHERE g.id != %s
           AND EXISTS (
                SELECT 1 FROM jsonb_each_text(g.name) t
                 WHERE lower(trim(t.value)) = 'expedientes'
           )
        """,
        (ours.id,),
    )
    duplicates = env["spreadsheet.dashboard.group"].browse([row[0] for row in cr.fetchall()])
    if not duplicates:
        return
    external_ids = duplicates.get_external_id()
    for group in duplicates:
        external_id = external_ids.get(group.id)
        if external_id and not external_id.startswith("__export__"):
            _logger.warning(
                "Grupo de tableros «%s» (%s) viene de otro módulo: no se junta "
                "con el de Expedientes.",
                group.name,
                external_id,
            )
            continue
        try:
            with cr.savepoint():
                group.dashboard_ids.write({"dashboard_group_id": ours.id})
                group.unlink()
        except Exception:
            _logger.warning(
                "No se pudo juntar el grupo de tableros «%s» con el de Expedientes.",
                group.name,
                exc_info=True,
            )
