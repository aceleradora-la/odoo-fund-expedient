# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def post_init_hook(env):
    """Genera access_token en expedientes existentes para enlaces portal.

    `_portal_ensure_token` es de registro único (lee `access_token` con
    `ensure_one`), así que se recorre uno por uno: llamarlo sobre el recordset
    completo rompía la instalación en cualquier base con más de un expediente.
    """
    expedients = env["fund.expedient"].sudo().search([("access_token", "=", False)])
    for expedient in expedients:
        expedient._portal_ensure_token()
