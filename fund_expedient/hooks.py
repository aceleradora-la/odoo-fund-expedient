# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def pre_init_hook(cr):
    """Añadir columna expedient_service_product_id a res_company antes de cargar el módulo.
    Evita UndefinedColumn cuando Odoo consulta res.company durante el upgrade.
    """
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS expedient_service_product_id INTEGER
    """)
