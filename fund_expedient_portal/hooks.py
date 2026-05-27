# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def post_init_hook(env):
    """Genera access_token en expedientes existentes para enlaces portal."""
    expedients = env["fund.expedient"].sudo().search([("access_token", "=", False)])
    if expedients:
        expedients._portal_ensure_token()
