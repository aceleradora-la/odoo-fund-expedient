# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Carga de contratos de Locación previos al módulo de Expedientes.

Cada contrato del JSON se crea como un expediente de Locación ya en la etapa
final, con una línea (proveedor, partida, fechas, importe), para que entre en
la proyección mensual y en el tablero de Contrataciones.

Uso, desde la shell de odoo.sh (o cualquier `odoo-bin shell`):

    MIGRACION_JSON=~/contratos_previos.json \\
        odoo-bin shell --no-http < migrar_contratos_previos.py

Por defecto corre en MODO PRUEBA: hace todo, informa y deshace (rollback).
Para grabar, agregar MIGRACION_GRABAR=1. Es idempotente: un contrato cuyo
número ya existe se saltea, así que se puede volver a correr tras corregir.

El JSON no se versiona: tiene datos personales (nombres, CUIT, honorarios).

Qué hace con cada contrato:
- Proveedor: lo busca POR CUIT en esta base (no por ID: los ID cambian entre
  producción y pre-prod). Entre contactos con el mismo CUIT gana el que ya se
  usó como proveedor, igual que el buscador por CUIT del expediente.
- Partida: cuenta analítica por código, dentro del plan configurado para
  Expedientes.
- Solicitante: el empleado indicado para las iniciales del gerente (define el
  sector requirente en los reportes).
- Tipo: «Locación de Servicios/Obra — contratos previos», que se crea si no
  existe, con dos etapas (En progreso → Aprobado, la final). La etapa previa
  existe para poder reabrir y corregir: un expediente en la etapa final no se
  edita y, sin etapa anterior, tampoco se podría reabrir.
- Número: el del JSON (LOC-2026-001A...). No consume la secuencia EXP.
"""

import json
import os
from collections import Counter
from datetime import date

GRABAR = os.environ.get("MIGRACION_GRABAR") == "1"
JSON_PATH = os.path.expanduser(os.environ.get("MIGRACION_JSON", "~/contratos_previos.json"))

TYPES = {
    "service_lease": "Locación de Servicios — contratos previos",
    "work_lease": "Locación de Obra — contratos previos",
}

env = env  # noqa: F821  (lo inyecta `odoo-bin shell`)
# Sin seguimiento ni suscripciones: la descripción ya deja constancia de que
# el contrato es una migración, y 200 notas «creado» no aportan nada.
Expedient = env["fund.expedient"].with_context(
    tracking_disable=True, mail_create_nosubscribe=True, mail_create_nolog=True
)
Partner = env["res.partner"].with_context(active_test=False)
Employee = env["hr.employee"].with_context(active_test=False)
Analytic = env["account.analytic.account"]
company = env.company


def digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def find_partner(cuit):
    d = digits(cuit)
    if len(d) != 11:
        return Partner.browse(), "CUIT inválido"
    formatted = f"{d[:2]}-{d[2:10]}-{d[10]}"
    found = Partner.search(["|", ("vat", "=", d), ("vat", "=", formatted)])
    if not found:
        return found, "no existe un contacto con ese CUIT"
    if len(found) == 1:
        return found, ""
    used = found.filtered(lambda p: p.supplier_rank > 0)
    if len(used) == 1:
        return used, ""
    return Partner.browse(), f"{len(found)} contactos con ese CUIT y no se puede elegir"


def find_analytic(code, plan):
    domain = [("code", "=", code)]
    if plan:
        domain.append(("plan_id", "child_of", plan.id))
    found = Analytic.search(domain)
    if len(found) == 1:
        return found, ""
    return Analytic.browse(), (
        f"no hay cuenta analítica con código {code}" if not found
        else f"{len(found)} cuentas analíticas con código {code}"
    )


def find_employee(name):
    if not name:
        return Employee.browse(), "sin empleado asignado a esas iniciales"
    found = Employee.search([("name", "=ilike", name.strip())])
    if len(found) == 1:
        return found, ""
    return Employee.browse(), (
        f"no hay un empleado llamado «{name}»" if not found
        else f"{len(found)} empleados llamados «{name}»"
    )


def ensure_type(kind):
    Type = env["fund.expedient.type"]
    expedient_type = Type.search([("name", "=", TYPES[kind])], limit=1)
    if expedient_type:
        return expedient_type
    first = env.ref("fund_expedient.stage_expedient_in_progress")
    final = env.ref("fund_expedient.stage_expedient_approved")
    return Type.create({
        "name": TYPES[kind],
        "operation_type": "expense",
        "contract_kind": kind,
        "stage_assign_ids": [
            (0, 0, {"stage_id": first.id, "sequence": 1}),
            (0, 0, {"stage_id": final.id, "sequence": 2, "is_final_stage": True}),
        ],
    })


# ----------------------------------------------------------------------
with open(JSON_PATH, encoding="utf-8") as fh:
    payload = json.load(fh)
contracts = payload["contratos"]
managers = payload.get("gerentes", {})

plan = env["fund.expedient.config"].get_analytic_plan(company)
final_stage = env.ref("fund_expedient.stage_expedient_approved")
types = {kind: ensure_type(kind) for kind in TYPES}

stats = Counter()
problems = []
created = Expedient.browse()
for c in contracts:
    number = c["numero"]
    if Expedient.search_count([("number", "=", number)]):
        stats["ya existía (salteado)"] += 1
        continue
    partner, p_err = find_partner(c["cuit"])
    analytic, a_err = find_analytic(c["partida"], plan)
    employee, e_err = find_employee(managers.get(c["gerente"]))
    errors = [e for e in (p_err, a_err, e_err) if e]
    if errors:
        stats["con problemas (no se crea)"] += 1
        problems.append((number, c["consultor"], "; ".join(errors)))
        continue
    start = date.fromisoformat(c["fecha_inicio"])
    end = date.fromisoformat(c["fecha_fin"])
    expedient = Expedient.create({
        "number": number,
        "type_id": types[c["locacion"]].id,
        "stage_id": final_stage.id,
        "company_id": company.id,
        "requestor_id": employee.id,
        "request_date": start,
        "date_done": start,
        "analytic_account_id": analytic.id,
        "recommended_supplier_ids": [(6, 0, partner.ids)],
        "contract_object": c["objeto"],
        "description": c["descripcion"],
        "line_ids": [(0, 0, {
            "name": c["linea"],
            "product_qty": c["meses"],
            "price_unit_estimated": c["monto_mensual"],
            "date_start": start,
            "date_end": end,
            "analytic_account_id": analytic.id,
            "recommended_supplier_ids": [(6, 0, partner.ids)],
        })],
    })
    created |= expedient
    stats["creado"] += 1

# ----------------------------------------------------------------------
env.flush_all()
print("\n" + "=" * 72)
print("GRABADO" if GRABAR else "MODO PRUEBA — no se grabó nada")
print("=" * 72)
for key, n in sorted(stats.items()):
    print(f"  {key}: {n}")
if created:
    total = sum(created.mapped("line_ids.amount_estimated_line"))
    print(f"  importe total creado: {total:,.2f}")
    print(f"  finalizados (entran en la proyección): {sum(created.mapped('stage_is_final'))} de {len(created)}")
if problems:
    print("\nCONTRATOS CON PROBLEMAS:")
    for number, who, err in problems:
        print(f"  {number}  {who}: {err}")

if GRABAR:
    env.cr.commit()
    print("\nCambios confirmados.")
else:
    env.cr.rollback()
    print("\nDeshecho. Para grabar: MIGRACION_GRABAR=1")
