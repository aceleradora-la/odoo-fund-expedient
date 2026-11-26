# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Configura los tipos de expediente según la matriz de circuitos (Excel v1).

Ver `PLAN_TIPOS_EXPEDIENTE.md`. Carga todo lo decidido hasta el 2026-11-19 y
las etapas que faltaban respecto del Excel:

1.  Tipos de documento *Disposición firmada*, *Resolución firmada*, *Nota
    firmada* y *Constancia de pago* (las disposiciones y resoluciones se
    firman por fuera de Odoo y se suben como documento).
2.  Nombres de etapas mal escritos («FIRNA», «DISPOSICION»).
3.  Etapa final (*DOCUMENTO CONTRACTUAL*) en Licitación privada, pública y
    Prórroga.
4.  Disposición / Resolución firmada obligatoria en cada etapa de firma.
5.  Validación de requerimiento y de SG para Dirección Ejecutiva, Auditoría
    Interna y Asesor Estratégico (Juan Cruz), que no tenían.
6.  Monto máximo de la Compulsa abreviada: 4.000 (en la moneda del tipo, UF).
7.  Etapas de cierre (Declarar Fracasado / Desierto / Dejar sin efecto) en
    Compulsa, Contratación directa y Licitación privada y pública, operadas
    por Compras.
8.  Licitación pública: *DICTAMEN LEGAL (2do)* antes de la firma de la
    resolución que adjudica.
9.  Aumento y Disminución: el mismo circuito que Prórroga.
10. Reconocimiento excepcional de gastos (devengados): verificación de la
    documentación y proyecto de acto, firma del acto y pago.
11. Tipos nuevos: Beneficios del personal, Reconocimiento excepcional -
    erogaciones previas, y Suscripciones y licencias digitales.
12. Regímenes de Reconocimiento excepcional y de Beneficios (Acta 61): la SG
    de los reconocimientos la autoriza también el Director Ejecutivo; el acto
    se firma por niveles (Anexo I); documentos obligatorios del requerimiento;
    *TRÁMITE CONCLUIDO* después del pago / la acreditación; la firma de
    Beneficios es solo del Director.
13. Etapa inicial de cada tipo: la opera el solicitante y quien crea queda
    como responsable, en vez de «Usuario interno» / «Expedientes / Usuario»
    (que suscribía a todos los usuarios como seguidores de cada expediente).
14. SERVICIOS y ADENDA SERVICIOS: *TRÁMITE CONCLUIDO* después de la etapa
    final actual (que deja de serlo), operada por AyF. Los expedientes que
    estaban cerrados en la etapa final vieja pasan a *TRÁMITE CONCLUIDO*
    (solo cambia la etapa; quedan cerrados, con su fecha de cierre).
15. OBRAS (locación de obra, mismo circuito que SERVICIOS) y AUSPICIOS A
    EVENTOS (evaluación de Dirección Ejecutiva, convenio firmado, pago y
    acreditación de la contraprestación), que no tenían etapas.

NO toca: quién opera las etapas que ya existen, los montos del art. 9, ni
documentos obligatorios fuera de las firmas, el pago y el requerimiento de los
regímenes de la sección 12 (pendientes de validar).

Es idempotente: busca por nombre y solo crea o corrige lo que falta; se puede
correr varias veces. No toca expedientes, salvo los de la sección 14; avisa si
alguno queda en una etapa que deja de estar en el circuito de su tipo (y en
ese caso no la saca).

Uso, desde la shell de odoo.sh (o cualquier `odoo-bin shell`):

    odoo-bin shell --no-http --log-level=warn < configurar_tipos_expediente.py

Por defecto corre en MODO PRUEBA: hace todo, informa y deshace (rollback).
Para grabar, agregar TIPOS_GRABAR=1.
"""

import os

from odoo import models

GRABAR = os.environ.get("TIPOS_GRABAR") == "1"
env = env  # noqa: F821  (la provee odoo-bin shell)
# Los nombres de etapas, grupos y tipos se buscan como los ven los usuarios.
LANG = "es_AR" if env["res.lang"]._lang_get("es_AR") else (env.lang or "en_US")
env = env(context=dict(env.context, lang=LANG, tracking_disable=True))

Stage = env["fund.expedient.stage"]
Type = env["fund.expedient.type"]
Assign = env["fund.expedient.type.stage.assign"]
DocType = env["fund.expedient.document.type"]
Group = env["res.groups"]
Expedient = env["fund.expedient"]
Tier = env["tier.definition"] if "tier.definition" in env else None

cambios = []
avisos = []


def hecho(msg):
    cambios.append(msg)
    print("  +", msg)


def aviso(msg):
    avisos.append(msg)
    print("  !", msg)


def seccion(titulo):
    print(f"\n== {titulo}")


def etapa(nombre):
    rec = Stage.search([("name", "=", nombre)], limit=1)
    if not rec:
        raise SystemExit(f"No existe la etapa «{nombre}»")
    return rec


def tipo(nombre):
    rec = Type.search([("name", "=", nombre)], limit=1)
    if not rec:
        raise SystemExit(f"No existe el tipo de expediente «{nombre}»")
    return rec


def grupo(nombre):
    rec = Group.search([("name", "=", nombre)], limit=1) or Group.with_context(
        lang="en_US"
    ).search([("name", "=", nombre)], limit=1)
    if not rec:
        raise SystemExit(f"No existe el grupo «{nombre}»")
    return rec


def asignacion(tipo_rec, etapa_rec):
    return Assign.search(
        [("type_id", "=", tipo_rec.id), ("stage_id", "=", etapa_rec.id)], limit=1
    )


def asegurar_etapa(nombre, parecida):
    """Crea la etapa si no existe, con el tipo de estado de una parecida."""
    rec = Stage.search([("name", "=", nombre)], limit=1)
    if rec:
        return rec
    rec = Stage.create(
        {
            "name": nombre,
            "state_type": parecida.state_type,
            "spend_request_mode": "none",
            "sequence": parecida.sequence,
        }
    )
    hecho(f"etapa nueva «{nombre}»")
    return rec


def asegurar_doc(nombre, secuencia):
    rec = DocType.search([("name", "=", nombre)], limit=1)
    if rec:
        return rec
    rec = DocType.create({"name": nombre, "sequence": secuencia})
    hecho(f"tipo de documento «{nombre}»")
    return rec


def escribir(rec, vals, etiqueta):
    """Escribe solo lo que cambia (para que el informe diga lo que hizo)."""
    nuevos = {}
    for campo, valor in vals.items():
        actual = rec[campo]
        if rec._fields[campo].type in ("many2many", "one2many"):
            ids = None
            if valor and valor[0][0] == 6:
                ids = valor[0][2]
            elif valor and valor[0][0] == 5:
                ids = []
            if ids is not None and set(actual.ids) == set(ids):
                continue
        elif rec._fields[campo].type == "many2one":
            if actual.id == (valor or False):
                continue
        elif actual == valor:
            continue
        nuevos[campo] = valor
    if nuevos:
        rec.write(nuevos)
        hecho(f"{etiqueta}: {', '.join(sorted(nuevos))}")


def circuito(tipo_rec, pasos):
    """Deja el circuito del tipo con estas etapas, en este orden.

    `pasos`: lista de (etapa, plantilla, valores). Si la etapa no está en el
    tipo se agrega copiando `plantilla` (una asignación existente, para heredar
    solapas visibles y campos ocultos) con `valores` encima. Si ya está, solo
    se ajusta la secuencia y lo indicado en `valores`.
    """
    for orden, (etapa_rec, plantilla, valores) in enumerate(pasos, start=1):
        valores = dict(valores or {}, sequence=orden * 10)
        actual = asignacion(tipo_rec, etapa_rec)
        if actual:
            escribir(actual, valores, f"{tipo_rec.name} / {etapa_rec.name}")
            continue
        if plantilla:
            plantilla.copy(dict(valores, type_id=tipo_rec.id, stage_id=etapa_rec.id))
        else:
            Assign.create(dict(valores, type_id=tipo_rec.id, stage_id=etapa_rec.id))
        hecho(f"{tipo_rec.name}: agrega «{etapa_rec.name}» (orden {orden})")


def operan(*grupos):
    return {"group_ids": [(6, 0, [g.id for g in grupos])], "use_requestor": False}


# ---------------------------------------------------------------------------
print("MODO GRABAR" if GRABAR else "MODO PRUEBA (no graba)")

seccion("1. Tipos de documento")
DISPO = asegurar_doc("Disposición firmada", 50)
RESO = asegurar_doc("Resolución firmada", 51)
NOTA = asegurar_doc("Nota firmada", 52)
PAGO_DOC = asegurar_doc("Constancia de pago", 53)
# Requerimiento de los regímenes de Reconocimiento (arts. 11 y 17) y de
# Beneficios (art. 5); conformidad de la prestación (art. 18 g).
FACTURA = asegurar_doc("Factura", 54)
CUIT_CBU = asegurar_doc("Constancia de CUIT y CBU", 55)
PROPUESTA = asegurar_doc("Propuesta o presupuesto", 56)
PROYECTO = asegurar_doc("Proyecto de acto o convenio", 57)
CONFORMIDAD = asegurar_doc("Conformidad de recepción", 58)

seccion("2. Nombres de etapas")
for viejo, nuevo in (
    ("FIRNA RESOLUCIÓN (2da)", "FIRMA RESOLUCIÓN (2da)"),
    ("FIRMA DISPOSICION (2da)", "FIRMA DISPOSICIÓN (2da)"),
):
    rec = Stage.search([("name", "=", viejo)], limit=1)
    if rec:
        for lang in {LANG, "en_US"}:
            rec.with_context(lang=lang).name = nuevo
        hecho(f"etapa «{viejo}» → «{nuevo}»")

# Etapas existentes
PEDIDO = etapa("PEDIDO")
INICIO = etapa("INICIO DE EXPTE.")
CERTIFICA = etapa("CERTIFICA FONDOS")
INFORME = etapa("INFORME TÉCNICO")
AFECTACION = etapa("AFECTACIÓN DEFINITIVA")
DICTAMEN_1 = etapa("DICTAMEN LEGAL (1ro)")
DICTAMEN_2 = etapa("DICTAMEN LEGAL (2do)")
FIRMA_DISPO_1 = etapa("FIRMA DISPOSICIÓN (1ra)")
FIRMA_DISPO_2 = etapa("FIRMA DISPOSICIÓN (2da)")
FIRMA_RESO_1 = etapa("FIRMA RESOLUCIÓN (1ra)")
FIRMA_RESO_2 = etapa("FIRMA RESOLUCIÓN (2da)")
FIRMA_CEO = etapa("FIRMA DISPO CEO")
NOTIF_OFERENTES = etapa("NOTIFICACIÓN A OFERENTES")
DOC_CONTRACTUAL = etapa("DOCUMENTO CONTRACTUAL")
CIERRES = [etapa("Declarar Fracasado"), etapa("Declarar Desierto"), etapa("Dejar sin efecto")]

COMPULSA = tipo("COMPULSA ABREVIADA")
DIRECTA = tipo("CONTRATACIÓN DIRECTA")
PRIVADA = tipo("LICITACIÓN PRIVADA")
PUBLICA = tipo("LICITACIÓN PÚBLICA")
PRORROGA = tipo("PRÓRROGA")
AUMENTO = tipo("AUMENTO")
DISMINUCION = tipo("DISMINUCIÓN")
RECONOCIMIENTO = tipo("RECONOCIMIENTO EXCEPCIONAL DE GASTOS")

COMPRAS = grupo("FS - Compras")
AYF = grupo("FS - Administración y Finanzas")
LEGALES = grupo("FS - Legales")
DIRECCION = grupo("FS - Direccion General")
PRESIDENCIA = grupo("FS - Presidencia (Secretaria)")
RRHH = grupo("FS - Recursos Humanos")

seccion("3. Etapa final")
for t in (PRIVADA, PUBLICA, PRORROGA):
    a = asignacion(t, DOC_CONTRACTUAL)
    if a:
        escribir(a, {"is_final_stage": True}, f"{t.name} / {DOC_CONTRACTUAL.name}")

seccion("4. Disposición / Resolución firmada en las firmas")
for t, e, doc in (
    (COMPULSA, FIRMA_DISPO_1, DISPO),
    (DIRECTA, FIRMA_DISPO_1, DISPO),
    (PRIVADA, FIRMA_DISPO_1, DISPO),
    (PRIVADA, FIRMA_CEO, DISPO),
    (PRIVADA, FIRMA_DISPO_2, DISPO),
    (PUBLICA, FIRMA_RESO_1, RESO),
    (PUBLICA, FIRMA_CEO, DISPO),
    (PUBLICA, FIRMA_RESO_2, RESO),
    (PRORROGA, FIRMA_DISPO_1, DISPO),
):
    a = asignacion(t, e)
    if a and doc not in a.required_document_type_ids:
        a.required_document_type_ids = [(4, doc.id)]
        hecho(f"{t.name} / {e.name}: exige «{doc.name}»")

seccion("5. Validaciones de Dirección Ejecutiva, Auditoría y Asesor")
if Tier is None:
    aviso("tier.definition no está instalado: se saltea")
else:
    Department = env["hr.department"]

    def depto(nombre):
        rec = Department.search([("complete_name", "=", nombre)], limit=1)
        if not rec:
            raise SystemExit(f"No existe el departamento «{nombre}»")
        return rec

    DE = depto("Dirección Ejecutiva")
    AUDITORIA = depto("Dirección Ejecutiva / Auditoria Interna")
    ASESOR = depto("Dirección Ejecutiva / Asesor Estratégico")

    def nivel(nombre, desde, dominio, **extra):
        if Tier.with_context(active_test=False).search([("name", "=", nombre)], limit=1):
            return
        fuente = Tier.search([("name", "=", desde)], limit=1)
        if not fuente:
            aviso(f"no está la regla «{desde}» para copiar «{nombre}»")
            return
        fuente.copy(dict(extra, name=nombre, definition_domain=dominio))
        hecho(f"regla de aprobación «{nombre}»")

    nivel(
        "Validación Pedido/Informe Técnico Auditoría y Asesor Estratégico",
        "Validación Pedido/Informe Técnico Comunicaciones",
        f'["&", ("requestor_department_id", "in", [{AUDITORIA.id}, {ASESOR.id}]), '
        f'("stage_id", "in", [{PEDIDO.id}, {INFORME.id}])]',
    )
    areas = f"[{DE.id}, {AUDITORIA.id}, {ASESOR.id}]"
    nivel(
        "Validación SG Preventiva - Dirección Ejecutiva, Auditoría y Asesor",
        "Validación SG Preventiva -  Comunicaciones",
        f'["&", ("spend_state", "=", "preventiva"), ("requestor_department_id", "in", {areas})]',
    )
    nivel(
        "Validación SG Definitiva - Dirección Ejecutiva, Auditoría y Asesor",
        "Validación SG Definitiva - Comunicaciones",
        f'["&", "&", "|", ("amount_diff_pct", ">=", 30), ("preventiva_state", "!=", "approved"), '
        f'("requestor_department_id", "in", {areas}), ("spend_state", "=", "definitiva")]',
    )

seccion("6. Monto máximo de la Compulsa")
escribir(COMPULSA, {"max_amount_unit": 4000.0}, COMPULSA.name)

seccion("7. Etapas de cierre")
for t in (COMPULSA, DIRECTA, PRIVADA, PUBLICA):
    for orden, cierre in enumerate(CIERRES, start=1):
        if not asignacion(t, cierre):
            Assign.create(
                {
                    "type_id": t.id,
                    "stage_id": cierre.id,
                    "sequence": 900 + orden,
                    "group_ids": [(6, 0, COMPRAS.ids)],
                }
            )
            hecho(f"{t.name}: agrega «{cierre.name}»")

seccion("8. Licitación pública: dictamen legal antes de adjudicar")
# Se inserta después de la afectación definitiva y se renumera el circuito
# (las etapas de cierre no cuentan: van aparte, al final).
if not asignacion(PUBLICA, DICTAMEN_2):
    flujo = PUBLICA.stage_assign_ids.filtered(
        lambda a: not a.stage_id.final_outcome_type_id
    ).sorted(lambda a: (a.sequence, a.id))
    nuevo = asignacion(PUBLICA, DICTAMEN_1).copy(
        {
            "type_id": PUBLICA.id,
            "stage_id": DICTAMEN_2.id,
            "group_ids": [(6, 0, LEGALES.ids)],
            "required_document_type_ids": [(5, 0, 0)],
        }
    )
    hecho(f"{PUBLICA.name}: agrega «{DICTAMEN_2.name}» después de «{AFECTACION.name}»")
    orden = []
    for a in flujo:
        orden.append(a)
        if a.stage_id == AFECTACION:
            orden.append(nuevo)
    if nuevo not in orden:
        orden.append(nuevo)
        aviso(f"{PUBLICA.name}: no tiene «{AFECTACION.name}»; el dictamen queda al final")
    for i, a in enumerate(orden, start=1):
        if a.sequence != i * 10:
            a.sequence = i * 10
    hecho(f"{PUBLICA.name}: circuito renumerado")

seccion("9. Aumento y Disminución (circuito de Prórroga)")
for t in (AUMENTO, DISMINUCION):
    for a in PRORROGA.stage_assign_ids.sorted(lambda r: (r.sequence, r.id)):
        if not asignacion(t, a.stage_id):
            a.copy({"type_id": t.id})
            hecho(f"{t.name}: agrega «{a.stage_id.name}»")
        else:
            escribir(asignacion(t, a.stage_id), {"sequence": a.sequence}, f"{t.name} / {a.stage_id.name}")
if DISMINUCION.approval_currency_id != PRORROGA.approval_currency_id:
    aviso(
        f"DISMINUCIÓN está en {DISMINUCION.approval_currency_id.name} y Prórroga en "
        f"{PRORROGA.approval_currency_id.name}: a definir (no se cambia)."
    )

seccion("10. Reconocimiento excepcional de gastos (devengados)")
VERIFICACION = asegurar_etapa("VERIFICACIÓN DOC. Y PROYECTO DE ACTO", DICTAMEN_1)
FIRMA_ACTO = asegurar_etapa("FIRMA DEL ACTO ADMINISTRATIVO", FIRMA_DISPO_1)
PAGO = asegurar_etapa("PAGO", DOC_CONTRACTUAL)
INSTRUMENTACION = asegurar_etapa("INSTRUMENTACIÓN DEL BENEFICIO", DOC_CONTRACTUAL)
ACREDITAR = asegurar_etapa("ACREDITAR PRESTACIÓN EFECTIVA", DOC_CONTRACTUAL)
EVALUACION_TEC = asegurar_etapa("EVALUACIÓN TÉCNICA Y ECONÓMICA", DICTAMEN_1)
FIRMA_NOTA = asegurar_etapa("FIRMA NOTA", FIRMA_DISPO_1)
# Cierre de los reconocimientos: en la etapa final no se controlan los
# documentos (de ahí no se avanza), así que la constancia de pago y la
# conformidad se exigen al salir de PAGO / ACREDITAR hacia esta (art. 22).
CONCLUIDO = asegurar_etapa("TRÁMITE CONCLUIDO", DOC_CONTRACTUAL)

# Plantillas: asignaciones existentes de las que se copian solapas y ocultos.
P_PEDIDO = asignacion(RECONOCIMIENTO, PEDIDO)
P_CERTIFICA = asignacion(RECONOCIMIENTO, CERTIFICA)
P_DICTAMEN = asignacion(RECONOCIMIENTO, DICTAMEN_1)
P_FINAL = asignacion(RECONOCIMIENTO, DOC_CONTRACTUAL) or P_DICTAMEN

no_final = {"is_final_stage": False}
final = {"is_final_stage": True}


def docs(*tipos):
    return {"required_document_type_ids": [(6, 0, [t.id for t in tipos])]}


sin_docs = {"required_document_type_ids": [(5, 0, 0)]}
firma_acto = dict(operan(DIRECCION, PRESIDENCIA), **docs(DISPO))
pago = dict(operan(AYF), **docs(PAGO_DOC))
pedido_reconocimiento = docs(FACTURA, CUIT_CBU)
concluido = dict(operan(AYF), **sin_docs, **final)

pasos_reconocimiento = [
    (PEDIDO, P_PEDIDO, pedido_reconocimiento),
    (VERIFICACION, P_DICTAMEN, dict(operan(COMPRAS), **no_final)),
    (CERTIFICA, P_CERTIFICA, None),
    (DICTAMEN_1, P_DICTAMEN, None),
    (FIRMA_ACTO, P_DICTAMEN, dict(firma_acto, **no_final)),
    (PAGO, P_FINAL, dict(pago, **no_final)),
]
circuito(RECONOCIMIENTO, pasos_reconocimiento)
# El cierre copia la asignación de PAGO (recién asegurada).
P_CIERRE = asignacion(RECONOCIMIENTO, PAGO)
circuito(RECONOCIMIENTO, pasos_reconocimiento + [(CONCLUIDO, P_CIERRE, concluido)])
viejo = asignacion(RECONOCIMIENTO, DOC_CONTRACTUAL)
if viejo:
    en_curso = Expedient.search_count(
        [("type_id", "=", RECONOCIMIENTO.id), ("stage_id", "=", DOC_CONTRACTUAL.id)]
    )
    if en_curso:
        escribir(viejo, {"is_final_stage": False, "sequence": 900}, f"{RECONOCIMIENTO.name} / {DOC_CONTRACTUAL.name}")
        aviso(
            f"{RECONOCIMIENTO.name}: {en_curso} expediente(s) en «{DOC_CONTRACTUAL.name}»; "
            "la etapa queda al final del circuito y deja de ser la final. Revisarlos."
        )
    else:
        viejo.unlink()
        hecho(f"{RECONOCIMIENTO.name}: saca «{DOC_CONTRACTUAL.name}» (la reemplaza PAGO)")

seccion("11. Tipos nuevos")
# La etapa final de Reconocimiento (PAGO) es la plantilla de las finales: la
# de DOCUMENTO CONTRACTUAL puede haberse sacado recién.
P_FINAL = asignacion(RECONOCIMIENTO, PAGO)


def tipo_nuevo(nombre):
    rec = Type.search([("name", "=", nombre)], limit=1)
    if rec:
        return rec
    rec = Type.create(
        {
            "name": nombre,
            "sequence": RECONOCIMIENTO.sequence + 1,
            "operation_type": RECONOCIMIENTO.operation_type,
            "contract_kind": "none",
            "approval_currency_id": RECONOCIMIENTO.approval_currency_id.id,
            "unit_mode": RECONOCIMIENTO.unit_mode,
        }
    )
    if RECONOCIMIENTO.sequence_id:
        rec.action_create_type_sequence()
    hecho(f"tipo nuevo «{nombre}»")
    return rec


pedido = {"allow_edit_type_id": True}

BENEFICIOS = tipo_nuevo("BENEFICIOS DEL PERSONAL")
circuito(
    BENEFICIOS,
    [
        (PEDIDO, P_PEDIDO, dict(operan(RRHH), **pedido, **docs(PROPUESTA, PROYECTO))),
        (CERTIFICA, P_CERTIFICA, None),
        (DICTAMEN_1, P_DICTAMEN, None),
        # Art. 8: firma solo el Director Ejecutivo; se instrumenta por
        # disposición o convenio, así que no se exige un documento fijo.
        (FIRMA_ACTO, P_DICTAMEN, dict(operan(DIRECCION), **sin_docs, **no_final)),
        (INSTRUMENTACION, P_FINAL, dict(operan(RRHH), required_document_type_ids=[(5, 0, 0)], **final)),
    ],
)

EROGACIONES = tipo_nuevo("RECONOCIMIENTO EXCEPCIONAL - EROGACIONES PREVIAS")
circuito(
    EROGACIONES,
    [
        (PEDIDO, P_PEDIDO, dict(pedido, **pedido_reconocimiento)),
        (VERIFICACION, P_DICTAMEN, dict(operan(COMPRAS), **no_final)),
        (CERTIFICA, P_CERTIFICA, None),
        (DICTAMEN_1, P_DICTAMEN, None),
        (FIRMA_ACTO, P_DICTAMEN, dict(firma_acto, **no_final)),
        (PAGO, P_FINAL, dict(pago, **no_final)),
        # Art. 18 g: el área requirente acredita la prestación. Con pago
        # escalonado (cap. IV) se vuelve a PAGO para el tramo siguiente.
        (
            ACREDITAR,
            P_FINAL,
            {"use_requestor": True, "group_ids": [(5, 0, 0)], **docs(CONFORMIDAD), **no_final},
        ),
        (CONCLUIDO, asignacion(RECONOCIMIENTO, CONCLUIDO), concluido),
    ],
)

SUSCRIPCIONES = tipo_nuevo("SUSCRIPCIONES Y LICENCIAS DIGITALES")
GIORDANO = env["res.users"].search([("name", "=", "Leandro Giordano")], limit=1)
if not GIORDANO:
    aviso("no está el usuario Leandro Giordano: la Evaluación técnica queda sin operador")
evaluacion = {
    "use_requestor": False,
    "group_ids": [(5, 0, 0)],
    "user_ids": [(6, 0, GIORDANO.ids)],
    "is_final_stage": False,
}
circuito(
    SUSCRIPCIONES,
    [
        (PEDIDO, P_PEDIDO, dict(pedido, **sin_docs)),
        (EVALUACION_TEC, P_DICTAMEN, evaluacion),
        (CERTIFICA, P_CERTIFICA, None),
        (FIRMA_NOTA, P_DICTAMEN, dict(operan(DIRECCION), required_document_type_ids=[(6, 0, NOTA.ids)], **no_final)),
        (PAGO, P_FINAL, dict(pago, **final)),
    ],
)

seccion("12. Validaciones de los reconocimientos excepcionales")
if Tier is None:
    aviso("tier.definition no está instalado: se saltea")
else:
    reconocimientos = f"[{RECONOCIMIENTO.id}, {EROGACIONES.id}]"
    # Arts. 12 c y 18 c: la SG la autorizan el Gerente de AyF (regla general)
    # y el Director Ejecutivo. Secuencia menor: firma después del Gerente.
    nivel(
        "Validación SG Preventiva - Reconocimiento excepcional (Director Ejecutivo)",
        "Validación SG Preventiva entre 1001 UF y 5000 UF",
        f'["&", ("spend_state", "=", "preventiva"), ("expedient_type_id", "in", {reconocimientos})]',
    )
    # Anexo I: quién firma el acto según el monto (en UF). El Director valida;
    # lo que firman el Tesorero / Presidente o el Consejo lo confirma
    # Presidencia (Secretaría) al subirlo.
    firma = f'("type_id", "in", {reconocimientos}), ("stage_id", "=", {FIRMA_ACTO.id})'
    nivel(
        "Firma acto Reconocimiento hasta 3000 UF - Director Ejecutivo",
        "Validación Pedido/Informe Técnico Comunicaciones",
        f'["&", "&", {firma}, ("amount_estimated_unit", "<=", 3000)]',
    )
    nivel(
        "Firma acto Reconocimiento entre 3000 y 5000 UF - Tesorero o Presidente - Subido",
        "SG Firmada por Presidente hasta 10000 UF - Subido",
        f'["&", "&", "&", {firma}, ("amount_estimated_unit", ">", 3000), '
        f'("amount_estimated_unit", "<=", 5000)]',
        reviewer_group_id=PRESIDENCIA.id,
    )
    nivel(
        "Firma acto Reconocimiento mayor a 5000 UF - Consejo - Subido",
        "SG Firmada por Presidente hasta 10000 UF - Subido",
        f'["&", "&", {firma}, ("amount_estimated_unit", ">", 5000)]',
        reviewer_group_id=PRESIDENCIA.id,
    )

seccion("13. Etapa inicial: el solicitante y quien crea, no todos los usuarios")
# Al crear, los usuarios que operan la etapa quedan como participantes y
# seguidores. Con la etapa inicial asignada a «Usuario interno» o a
# «Expedientes / Usuario», cada expediente nuevo suscribía a todos. Queda a
# cargo del solicitante, y quien lo crea (p. ej. Compras por otra área) queda
# como responsable. No cambia quién puede crear expedientes.
AMPLIOS = env.ref("base.group_user") | env.ref("fund_expedient.group_fund_expedient_user")
for t in Type.search([]):
    primera = t.stage_assign_ids.filtered(
        lambda a: not a.stage_id.final_outcome_type_id
    ).sorted(lambda a: (a.sequence, a.id))[:1]
    if primera and primera.group_ids & AMPLIOS:
        escribir(
            primera,
            {"group_ids": [(5, 0, 0)], "use_requestor": True, "assign_creator": True},
            f"{t.name} / {primera.stage_id.name}",
        )

seccion("14. TRÁMITE CONCLUIDO en SERVICIOS y ADENDA SERVICIOS")
# Como en los reconocimientos: la etapa final pasa a ser TRÁMITE CONCLUIDO,
# después de la que hoy es la final (FIRMA CONTRATO), y la opera AyF. Va antes
# de OBRAS, que copia el circuito de SERVICIOS.
SERVICIOS = tipo("SERVICIOS")
ADENDA = tipo("ADENDA SERVICIOS")
for t in (SERVICIOS, ADENDA):
    flujo = t.stage_assign_ids.filtered(
        lambda a: not a.stage_id.final_outcome_type_id
    ).sorted(lambda a: (a.sequence, a.id))
    cierre = flujo.filtered(lambda a: a.stage_id == CONCLUIDO)
    previas = flujo - cierre
    if not previas:
        aviso(f"{t.name}: no tiene etapas; se saltea")
        continue
    viejas_finales = previas.filtered("is_final_stage")
    valores = dict(
        concluido,
        user_ids=[(5, 0, 0)],
        assign_creator=False,
        sequence=max(previas.mapped("sequence")) + 10,
    )
    if cierre:
        escribir(cierre, valores, f"{t.name} / {CONCLUIDO.name}")
    else:
        # Copia la última etapa del propio tipo (solapas y campos ocultos).
        previas[-1].copy(dict(valores, type_id=t.id, stage_id=CONCLUIDO.id))
        hecho(f"{t.name}: agrega «{CONCLUIDO.name}» al final")
    for a in viejas_finales:
        # Los expedientes que ya estaban cerrados en esa etapa (contratos
        # firmados) pasan a CONCLUIDO, para que sigan cerrados y en la
        # proyección de contratos. Solo cambia la etapa: BaseModel.write
        # saltea los controles de avance, el responsable, los avisos y los
        # seguidores; la fecha de cierre original se conserva.
        cerrados = Expedient.with_context(active_test=False).search(
            [("type_id", "=", t.id), ("stage_id", "=", a.stage_id.id), ("state", "=", "done")]
        )
        escribir(a, no_final, f"{t.name} / {a.stage_id.name}")
        if not cerrados:
            continue
        models.BaseModel.write(cerrados, {"stage_id": CONCLUIDO.id})
        for e in cerrados:
            e.message_post(
                body=f"Pasa de «{a.stage_id.name}» a «{CONCLUIDO.name}», la nueva etapa "
                f"final de {t.name} (configuración de tipos de expediente).",
                subtype_xmlid="mail.mt_note",
            )
        hecho(
            f"{t.name}: {len(cerrados)} expediente(s) de «{a.stage_id.name}» pasan a "
            f"«{CONCLUIDO.name}»: {', '.join(cerrados.mapped(lambda e: e.number or str(e.id)))}"
        )

seccion("15. Obras y Auspicios a eventos")
OBRAS = tipo("OBRAS")
AUSPICIOS = tipo("AUSPICIOS A EVENTOS")


def numeracion(t):
    if not t.sequence_id:
        t.action_create_type_sequence()
        hecho(f"{t.name}: numeración propia")


# OBRAS es la locación de obra: el mismo circuito que SERVICIOS (locación de
# servicios), con su tipo de contrato y su moneda de aprobación.
escribir(
    OBRAS,
    {"contract_kind": "work_lease", "approval_currency_id": SERVICIOS.approval_currency_id.id},
    OBRAS.name,
)
for a in SERVICIOS.stage_assign_ids.sorted(lambda r: (r.sequence, r.id)):
    actual = asignacion(OBRAS, a.stage_id)
    if actual:
        escribir(
            actual,
            {"sequence": a.sequence, "is_final_stage": a.is_final_stage},
            f"{OBRAS.name} / {a.stage_id.name}",
        )
    else:
        a.copy({"type_id": OBRAS.id})
        hecho(f"{OBRAS.name}: agrega «{a.stage_id.name}»")
numeracion(OBRAS)

# AUSPICIOS: la Fundación aporta fondos a un evento de terceros a cambio de
# una contraprestación (logo, espacio, etc.), que el área acredita al final.
EVAL_AUSPICIO = asegurar_etapa("EVALUACIÓN DEL AUSPICIO", DICTAMEN_1)
ACREDITAR_CONTRA = asegurar_etapa("ACREDITAR CONTRAPRESTACIÓN", DOC_CONTRACTUAL)
CONVENIO_AUSPICIO = asegurar_doc("Convenio de auspicio firmado", 59)
EVIDENCIA = asegurar_doc("Evidencia de la contraprestación", 60)
inicial = {"group_ids": [(5, 0, 0)], "use_requestor": True, "assign_creator": True}
circuito(
    AUSPICIOS,
    [
        (PEDIDO, P_PEDIDO, dict(inicial, **pedido, **sin_docs)),
        (EVAL_AUSPICIO, P_DICTAMEN, dict(operan(DIRECCION), **sin_docs, **no_final)),
        (CERTIFICA, P_CERTIFICA, None),
        (DICTAMEN_1, P_DICTAMEN, None),
        (FIRMA_ACTO, P_DICTAMEN, dict(operan(DIRECCION), **docs(CONVENIO_AUSPICIO), **no_final)),
        (PAGO, P_FINAL, dict(pago, **no_final)),
        (
            ACREDITAR_CONTRA,
            P_FINAL,
            {"use_requestor": True, "group_ids": [(5, 0, 0)], **docs(EVIDENCIA), **no_final},
        ),
        (CONCLUIDO, asignacion(RECONOCIMIENTO, CONCLUIDO), concluido),
    ],
)
numeracion(AUSPICIOS)

# ---------------------------------------------------------------------------
seccion("Resumen")
print(f"{len(cambios)} cambio(s), {len(avisos)} aviso(s).")
for t in (COMPULSA, DIRECTA, PRIVADA, PUBLICA, PRORROGA, AUMENTO, DISMINUCION,
          RECONOCIMIENTO, BENEFICIOS, EROGACIONES, SUSCRIPCIONES, SERVICIOS, ADENDA,
          OBRAS, AUSPICIOS):
    etapas = []
    for a in t.stage_assign_ids.sorted(lambda r: (r.sequence, r.id)):
        marca = " (final)" if a.is_final_stage else ""
        if a.stage_id.final_outcome_type_id:
            continue
        etapas.append(a.stage_id.name + marca)
    cierre = "sí" if t.stage_assign_ids.filtered("stage_id.final_outcome_type_id") else "no"
    tope = f", tope {t.max_amount_unit:,.0f}" if t.max_amount_unit else ""
    print(f"- {t.name}{tope} · cierres: {cierre}\n    " + " → ".join(etapas))

if GRABAR:
    env.cr.commit()
    print("\nGRABADO")
else:
    env.cr.rollback()
    print("\nMODO PRUEBA: se deshizo todo. Para grabar: TIPOS_GRABAR=1")
