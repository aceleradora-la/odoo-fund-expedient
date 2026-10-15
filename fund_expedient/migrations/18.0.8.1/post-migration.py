# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Ejecuta en ACTUALIZACIONES las migraciones que el hook solo corría al instalar.

`post_init_hook` únicamente se ejecuta cuando el módulo se instala por primera
vez; en un `-u` no se llama. Por eso las conversiones de datos incorporadas al
hook (tipos de documento, recálculo de comprometido/real) nunca llegaban a las
bases ya instaladas. Este script las invoca reutilizando las mismas funciones,
que son idempotentes: solo completan lo que falta.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.fund_expedient.hooks import (
    _migrate_document_flags_to_types,
    _recompute_expedient_commercial_amounts,
)


def migrate(cr, version):
    if not version:
        # Instalación nueva: de eso ya se encarga post_init_hook.
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_document_flags_to_types(cr, env)
    _recompute_expedient_commercial_amounts(env)
