# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Qué hay en la base de la migración de contratos previos. Solo lectura.

Uso, desde la shell de odoo.sh:

    odoo-bin shell --no-http --log-level=warn < revisar_migracion_contratos.py

Informa los tipos «— contratos previos», los expedientes de esos tipos (con
sus líneas e importes) y los contactos provisorios «CUIT …» que quedaron sin
datos del padrón. Termina con rollback: no cambia nada.
"""

import re

env = env  # noqa: F821  (lo inyecta `odoo-bin shell`)

TYPE_NAMES = (
    "Locación de Servicios — contratos previos",
    "Locación de Obra — contratos previos",
)

types = env["fund.expedient.type"].with_context(active_test=False).search([("name", "in", TYPE_NAMES)])
print("=" * 72)
print("TIPOS «contratos previos»:", ", ".join(f"{t.name} (id {t.id})" for t in types) or "ninguno")

expedients = env["fund.expedient"].sudo().with_context(active_test=False).search(
    [("type_id", "in", types.ids)], order="create_date, id"
)
lines = expedients.mapped("line_ids").filtered(lambda line: not line.display_type)
print(f"EXPEDIENTES de esos tipos: {len(expedients)}  —  líneas: {len(lines)}")
if expedients:
    print(f"  importe definitivo total: {sum(lines.mapped('amount_final_line')):,.2f}")
    print(f"  creados entre {min(expedients.mapped('create_date'))} y {max(expedients.mapped('create_date'))}")
    for exp in expedients:
        exp_lines = exp.line_ids.filtered(lambda line: not line.display_type)
        print(f"  {exp.number:<14} {len(exp_lines):>2} líneas  {exp.create_date}  {exp.stage_id.name}")

placeholder = re.compile(r"^CUIT \d{2}-\d{8}-\d$")
partners = env["res.partner"].sudo().with_context(active_test=False).search([("name", "=like", "CUIT %")])
partners = partners.filtered(lambda p: placeholder.match(p.name or ""))
print(f"CONTACTOS PROVISORIOS «CUIT …» sin datos del padrón: {len(partners)}")
for partner in partners:
    print(f"  id {partner.id:<7} {partner.name}  creado {partner.create_date}")

print("=" * 72)
env.cr.rollback()
