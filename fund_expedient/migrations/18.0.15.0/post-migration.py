# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Expedientes que ya estaban en su etapa final pasan a «Finalizado».

`state` es un cálculo almacenado y agregarle una dependencia no recalcula
las filas existentes. Se corrige por SQL; como fecha de cierre se toma la
última modificación, que en la práctica es el cambio a la etapa final.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE fund_expedient
           SET state = 'done',
               date_done = COALESCE(date_done, write_date::date)
         WHERE stage_is_final IS TRUE
           AND COALESCE(state, '') <> 'cancel'
        """
    )
