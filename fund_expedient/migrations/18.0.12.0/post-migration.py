# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Migra los tipos de disposición de lista fija a tabla.

`fund.expedient.disposition.disposition_type` y `fund.expedient.stage.
final_outcome` eran campos Selection. Ahora son Many2one a
`fund.expedient.disposition.type`. Las columnas viejas siguen en la base
(Odoo no las borra al quitar el campo del modelo), así que se leen por SQL y
se traducen usando el `code` de los tipos, que coincide con el valor anterior.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.fund_expedient.hooks import _column_exists, _table_exists


def _type_ids_by_code(env):
    types = env["fund.expedient.disposition.type"].search([])
    return {t.code: t.id for t in types if t.code}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    by_code = _type_ids_by_code(env)
    if not by_code:
        return

    # 1) Disposiciones: valor viejo -> tipo.
    if _table_exists(cr, "fund_expedient_disposition") and _column_exists(
        cr, "fund_expedient_disposition", "disposition_type"
    ):
        for code, type_id in by_code.items():
            cr.execute(
                """
                UPDATE fund_expedient_disposition
                   SET disposition_type_id = %s
                 WHERE disposition_type_id IS NULL
                   AND disposition_type = %s
                """,
                (type_id, code),
            )
    # Las que quedaron sin tipo (nulas o con un valor desconocido) pasan a
    # Adjudicación, que es el default y no cierra el expediente.
    adjudicacion = by_code.get("adjudicacion")
    if adjudicacion and _table_exists(cr, "fund_expedient_disposition"):
        cr.execute(
            """
            UPDATE fund_expedient_disposition
               SET disposition_type_id = %s
             WHERE disposition_type_id IS NULL
            """,
            (adjudicacion,),
        )

    # 2) Etapas: resultado final viejo -> tipo que cierra.
    if _table_exists(cr, "fund_expedient_stage") and _column_exists(
        cr, "fund_expedient_stage", "final_outcome"
    ):
        for code, type_id in by_code.items():
            cr.execute(
                """
                UPDATE fund_expedient_stage
                   SET final_outcome_type_id = %s
                 WHERE final_outcome_type_id IS NULL
                   AND final_outcome = %s
                """,
                (type_id, code),
            )
