# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Carga de contratos de Locación previos al módulo de Expedientes.

Cada expediente del JSON (el «Archivo» de la Fundación) se crea como un
expediente de Locación ya en la etapa final, con una línea por contrato
(consultor y tramo: proveedor, partida, fechas, importe), para que entre en
la proyección mensual y en el tablero de Contrataciones.

Uso, desde la shell de odoo.sh (o cualquier `odoo-bin shell`):

    MIGRACION_JSON=~/contratos_previos.json \\
        odoo-bin shell --no-http < migrar_contratos_previos.py

Por defecto corre en MODO PRUEBA: hace todo, informa y deshace (rollback).
Para grabar, agregar MIGRACION_GRABAR=1.

Es idempotente y se puede volver a correr tras corregir: un expediente que ya
existe no se recrea, pero se le agregan las líneas que todavía no tiene (un
contrato se identifica por proveedor + fecha de inicio + fecha de fin). Así,
los contratos que quedaron afuera por un CUIT pendiente se suman después.

El JSON no se versiona: tiene datos personales (nombres, CUIT, honorarios).

Qué resuelve en la base donde corre (por eso sirve igual en pre-prod y en
producción, aunque los ID difieran):
- Proveedor, POR CUIT. Entre contactos con el mismo CUIT gana el que ya se
  usó como proveedor, igual que el buscador por CUIT del expediente.
- Partida: cuenta analítica por código, dentro del plan configurado para
  Expedientes.
- Solicitante: el empleado indicado para las iniciales del gerente, sin
  importar tildes ni mayúsculas (define el sector requirente).
- Tipo: «Locación de Servicios/Obra — contratos previos», que se crea si no
  existe, con dos etapas (En progreso → Aprobado, la final). La etapa previa
  permite reabrir y corregir: en la etapa final no se edita y, sin etapa
  anterior, tampoco se podría reabrir.
- Número: el Archivo de la planilla (p. ej. 37/26). No consume la secuencia
  EXP; el importador estándar no sirve para esto porque omite los campos de
  solo lectura, como el número.
"""

import json
import os
import unicodedata
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
# es una migración, y cientos de notas «creado» no aportan nada.
quiet = {"tracking_disable": True, "mail_create_nosubscribe": True, "mail_create_nolog": True}
Expedient = env["fund.expedient"].with_context(**quiet)
Line = env["fund.expedient.line"].with_context(**quiet)
Partner = env["res.partner"].with_context(active_test=False)
Employee = env["hr.employee"].with_context(active_test=False)
Analytic = env["account.analytic.account"]
company = env.company


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def find_partner(cuit):
    d = digits(cuit)
    if len(d) != 11:
        return Partner.browse(), "CUIT inválido o vacío"
    formatted = f"{d[:2]}-{d[2:10]}-{d[10]}"
    found = Partner.search(["|", ("vat", "=", d), ("vat", "=", formatted)])
    if not found:
        return found, f"no existe un contacto con CUIT {formatted}"
    if len(found) == 1:
        return found, ""
    used = found.filtered(lambda p: p.supplier_rank > 0)
    if len(used) == 1:
        return used, ""
    return Partner.browse(), f"{len(found)} contactos con CUIT {formatted} y no se puede elegir"


analytic_cache = {}


def find_analytic(code, plan):
    if code not in analytic_cache:
        domain = [("code", "=", code)]
        if plan:
            domain.append(("plan_id", "child_of", plan.id))
        found = Analytic.search(domain)
        analytic_cache[code] = (
            (found, "") if len(found) == 1
            else (Analytic.browse(), f"no hay cuenta analítica con código {code}" if not found
                  else f"{len(found)} cuentas analíticas con código {code}")
        )
    return analytic_cache[code]


employee_cache = {}


def find_employee(name):
    """Por nombre, sin importar tildes, mayúsculas ni el orden de las palabras."""
    if not name:
        return Employee.browse(), "sin empleado para esas iniciales"
    if name not in employee_cache:
        wanted = norm(name)
        tokens = wanted.split()
        candidates = Employee.search([("name", "ilike", tokens[-1][:4])]) | Employee.search(
            [("name", "ilike", tokens[0][:4])]
        )
        exact = candidates.filtered(lambda e: norm(e.name) == wanted)
        loose = candidates.filtered(lambda e: all(t in norm(e.name).split() for t in tokens))
        found = exact or loose
        employee_cache[name] = (
            (found, "") if len(found) == 1
            else (Employee.browse(), f"no hay un empleado «{name}»" if not found
                  else f"{len(found)} empleados coinciden con «{name}»")
        )
    return employee_cache[name]


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


def line_key(partner_id, start, end):
    return (partner_id, str(start), str(end))


# ----------------------------------------------------------------------
with open(JSON_PATH, encoding="utf-8") as fh:
    payload = json.load(fh)
managers = payload.get("gerentes", {})

plan = env["fund.expedient.config"].get_analytic_plan(company)
final_stage = env.ref("fund_expedient.stage_expedient_approved")
types = {kind: ensure_type(kind) for kind in TYPES}

stats = Counter()
problems = []
touched = Expedient.browse()
for exp in payload["expedientes"]:
    number = exp["numero"]
    employee, e_err = find_employee(managers.get(exp["gerente"]))
    header_analytic, h_err = find_analytic(exp["partida"], plan)

    # Líneas que se pueden resolver; las demás se informan y se saltean.
    ready = []
    for ln in exp["lineas"]:
        partner, p_err = find_partner(ln["cuit"])
        analytic, a_err = find_analytic(ln["partida"], plan)
        errors = [e for e in (p_err, a_err) if e]
        if errors:
            stats["líneas con problemas"] += 1
            problems.append((number, ln["consultor"], "; ".join(errors)))
            continue
        ready.append((ln, partner, analytic))

    existing = Expedient.search([("number", "=", number)], limit=1)
    if existing:
        have = {line_key(l.recommended_supplier_ids[:1].id, l.date_start, l.date_end)
                for l in existing.line_ids}
        new = [(ln, p, a) for ln, p, a in ready
               if line_key(p.id, ln["fecha_inicio"], ln["fecha_fin"]) not in have]
        stats["expedientes que ya existían"] += 1
        stats["líneas que ya existían"] += len(ready) - len(new)
        if not new:
            continue
        target = existing
    else:
        if e_err or h_err:
            stats["expedientes con problemas (no se crean)"] += 1
            problems.append((number, "(cabecera)", "; ".join(e for e in (e_err, h_err) if e)))
            continue
        if not ready:
            stats["expedientes sin líneas válidas (no se crean)"] += 1
            continue
        start = min(date.fromisoformat(ln["fecha_inicio"]) for ln, _p, _a in ready)
        target = Expedient.create({
            "number": number,
            "type_id": types[exp["locacion"]].id,
            "stage_id": final_stage.id,
            "company_id": company.id,
            "requestor_id": employee.id,
            "request_date": start,
            "date_done": start,
            "analytic_account_id": header_analytic.id,
            "contract_object": exp["objeto"],
            "description": exp["descripcion"],
        })
        stats["expedientes creados"] += 1
        new = ready

    # Líneas directo en el modelo de líneas: escribirlas a través del
    # expediente pasaría por el candado de etapa (cerrado = no se edita).
    for ln, partner, analytic in new:
        Line.create({
            "expedient_id": target.id,
            "name": ln["nombre"],
            "product_qty": ln["meses"],
            "price_unit_estimated": ln["monto_mensual"],
            "date_start": ln["fecha_inicio"],
            "date_end": ln["fecha_fin"],
            "analytic_account_id": analytic.id,
            "recommended_supplier_ids": [(6, 0, partner.ids)],
        })
    stats["líneas creadas"] += len(new)
    suppliers = target.line_ids.mapped("recommended_supplier_ids")
    target.with_context(skip_validation_check=True).write(
        {"recommended_supplier_ids": [(6, 0, suppliers.ids)]}
    )
    touched |= target

# ----------------------------------------------------------------------
env.flush_all()
print("\n" + "=" * 72)
print("GRABADO" if GRABAR else "MODO PRUEBA — no se grabó nada")
print("=" * 72)
for key, n in sorted(stats.items()):
    print(f"  {key}: {n}")
if touched:
    total = sum(touched.mapped("line_ids.amount_estimated_line"))
    print(f"  importe total en los expedientes cargados: {total:,.2f}")
    print(f"  finalizados (entran en la proyección): "
          f"{sum(touched.mapped('stage_is_final'))} de {len(touched)}")
if problems:
    print("\nPROBLEMAS (lo que no se cargó):")
    for number, who, err in problems:
        print(f"  {number:<14} {who}: {err}")

if GRABAR:
    env.cr.commit()
    print("\nCambios confirmados.")
else:
    env.cr.rollback()
    print("\nDeshecho. Para grabar: MIGRACION_GRABAR=1")
