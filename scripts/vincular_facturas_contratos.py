# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Vincula las facturas de los consultores a los contratos previos migrados.

Los expedientes de «Locación de Servicios/Obra — contratos previos» (ver
`migrar_contratos_previos.py`) nacen sin facturas: su real queda en cero y el
comprometido es el contrato completo. Este script busca las facturas de
proveedor que ya existen de cada consultor y las vincula a su expediente, con
lo que el real refleja lo facturado y el comprometido baja en esa medida.

Uso, desde la shell de odoo.sh (o cualquier `odoo-bin shell`):

    odoo-bin shell --no-http --log-level=warn < vincular_facturas_contratos.py

Por defecto corre en MODO PRUEBA: hace todo, informa y deshace (rollback).
Para grabar, agregar VINCULAR_GRABAR=1.

Regla de vinculación, por factura:
- Facturas y notas de crédito de proveedor, en borrador o publicadas (no
  canceladas), del consultor del contrato (se compara la empresa del
  contacto, así una factura emitida a nombre de un contacto hijo también
  cuenta).
- La fecha de la factura tiene que caer en el período de algún contrato de
  ese consultor, extendido GRACIA_DIAS días después del fin (los honorarios
  de un mes suelen facturarse a principios del siguiente). Por defecto 45;
  se cambia con VINCULAR_GRACIA_DIAS.
- Si el consultor tiene contratos en más de un expediente y la fecha cae en
  más de uno, gana el que la contiene sin contar la gracia; si sigue
  habiendo más de uno, la factura no se vincula y se informa.
- Las facturas que ya tienen un expediente (vinculadas a mano o por su OC)
  no se tocan: se informan.

Es idempotente: una factura ya vinculada no se vuelve a procesar.

Al vincular, el módulo hace lo mismo que al hacerlo a mano: completa la
cuenta analítica del expediente en las líneas de la factura que no tienen
distribución analítica, y recalcula comprometido y real. El informe dice en
cuántas facturas pasa eso.
"""

import os
from collections import Counter, defaultdict
from datetime import timedelta

GRABAR = os.environ.get("VINCULAR_GRABAR") == "1"
GRACIA_DIAS = int(os.environ.get("VINCULAR_GRACIA_DIAS", "45"))

env = env  # noqa: F821  (lo inyecta `odoo-bin shell`)

TYPE_NAMES = (
    "Locación de Servicios — contratos previos",
    "Locación de Obra — contratos previos",
)

types = env["fund.expedient.type"].with_context(active_test=False).search([("name", "in", TYPE_NAMES)])
expedients = env["fund.expedient"].with_context(active_test=False).search([("type_id", "in", types.ids)])
Move = env["account.move"]

# Contratos por consultor (empresa del contacto): (inicio, fin, expediente).
contracts = defaultdict(list)
for exp in expedients:
    for line in exp.line_ids.filtered(lambda l: not l.display_type and l.date_start and l.date_end):
        for partner in line.recommended_supplier_ids:
            contracts[partner.commercial_partner_id].append((line.date_start, line.date_end, exp))

stats = Counter()
problems = []
already = []
to_link = defaultdict(lambda: Move.browse())  # expediente -> facturas
for partner, periods in contracts.items():
    bills = Move.search(
        [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "!=", "cancel"),
            ("commercial_partner_id", "=", partner.id),
        ],
        order="invoice_date, id",
    )
    for bill in bills:
        bill_date = bill.invoice_date or bill.date
        if bill.expedient_ids:
            if not (bill.expedient_ids & expedients):
                already.append((bill, bill.expedient_ids))
            stats["facturas que ya tenían expediente (no se tocan)"] += 1
            continue
        if not bill_date:
            stats["facturas sin fecha (no se vinculan)"] += 1
            problems.append((bill, "sin fecha de factura"))
            continue
        candidates = {
            exp for start, end, exp in periods if start <= bill_date <= end + timedelta(days=GRACIA_DIAS)
        }
        if len(candidates) > 1:
            strict = {exp for start, end, exp in periods if start <= bill_date <= end}
            candidates = strict if len(strict) == 1 else candidates
        if not candidates:
            stats["facturas del consultor fuera del período de sus contratos"] += 1
            problems.append((bill, "fuera del período de los contratos"))
            continue
        if len(candidates) > 1:
            stats["facturas que caen en más de un expediente (no se vinculan)"] += 1
            problems.append(
                (bill, "cae en " + ", ".join(sorted(e.number for e in candidates)))
            )
            continue
        to_link[candidates.pop()] |= bill

linked = Move.browse()
with_analytic = 0
for exp, bills in to_link.items():
    for bill in bills:
        if bill.invoice_line_ids.filtered(lambda l: not l.display_type and not l.analytic_distribution):
            with_analytic += 1
    bills.write({"expedient_ids": [(4, exp.id)]})
    linked |= bills
stats["facturas vinculadas"] = len(linked)
stats["facturas a las que se les completa la analítica"] = with_analytic

env.flush_all()
touched = expedients.filtered(lambda e: e in to_link)
touched.invalidate_recordset()
touched._invalidate_commercial_computes()
env.flush_all()

print("\n" + "=" * 72)
print("GRABADO" if GRABAR else "MODO PRUEBA — no se grabó nada")
print(f"(gracia: {GRACIA_DIAS} días después del fin de cada contrato)")
print("=" * 72)
print(f"  contratos previos: {len(expedients)} expedientes, {len(contracts)} consultores")
for key, n in sorted(stats.items()):
    print(f"  {key}: {n}")
posted = linked.filtered(lambda m: m.state == "posted")
print(f"  importe vinculado (publicadas): {sum(posted.mapped(lambda m: -m.amount_total_signed)):,.2f}")
print(f"  borradores vinculados: {len(linked - posted)} (cuentan en el real al publicarse)")
print(
    f"  contratos previos — comprometido: {sum(expedients.mapped('amount_committed')):,.2f}"
    f"   real: {sum(expedients.mapped('amount_real')):,.2f}"
)

if touched:
    print("\nPOR EXPEDIENTE (contrato / real / comprometido / facturas):")
    for exp in touched.sorted("number"):
        contract = sum(exp.line_ids.mapped("amount_final_line"))
        flag = "  <-- facturado más que el contrato" if exp.amount_real > contract + 0.01 else ""
        print(
            f"  {exp.number:<10} {contract:>16,.2f} {exp.amount_real:>16,.2f} "
            f"{exp.amount_committed:>16,.2f}  {len(to_link[exp]):>3}{flag}"
        )
if problems:
    print("\nNO SE VINCULARON (revisar):")
    for bill, why in problems:
        print(
            f"  {bill.name or bill.ref or bill.id:<22} {bill.invoice_date or bill.date}  "
            f"{bill.partner_id.name[:30]:<30} {-bill.amount_total_signed:>14,.2f}  {why}"
        )
if already:
    print("\nYA TENÍAN OTRO EXPEDIENTE (no se tocaron):")
    for bill, exps in already:
        print(
            f"  {bill.name or bill.id:<22} {bill.invoice_date or bill.date}  "
            f"{bill.partner_id.name[:30]:<30} -> {', '.join(exps.mapped('number'))}"
        )

if GRABAR:
    env.cr.commit()
    print("\nCambios confirmados.")
else:
    env.cr.rollback()
    print("\nDeshecho. Para grabar: VINCULAR_GRABAR=1")
