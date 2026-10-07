# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Campo «Expedientes» de facturas, OC y pagos con expedientes ajenos.

Los expedientes solo los ven sus participantes (ver
`security/fund_expedient_privacy.xml`), pero quien carga una factura o una OC
tiene que poder vincularla a cualquiera, y ver a cuál está vinculada, aunque
no haya participado. Se expone solo el número —nunca el contenido—:

- el selector busca con `sudo` (`fund.expedient.name_search` con el contexto
  `fund_expedient_link_all`, que ponen las vistas de esos campos);
- al leer el documento se completan las etiquetas de los expedientes
  vinculados que las reglas ocultan: Odoo filtra los Many2many por las reglas
  del modelo relacionado (`link_web_read`);
- el vínculo se escribe con `sudo`, para que quitar una de esas etiquetas
  funcione y para que nunca se pierdan las que el usuario no ve
  (`link_write`).

Abrir el expediente sigue sujeto a las reglas.

Son funciones y no un mixin a propósito: un mixin agregado a un modelo
existente queda por debajo de él en la herencia, y su `write` saltearía el
del modelo (y el seguimiento de cambios del chatter).
"""

FIELD = "expedient_ids"


def link_web_read(records, result, specification):
    """Completa en `result` (salida de `web_read`) las etiquetas ocultas."""
    spec = specification.get(FIELD)
    if spec is None or records.env.su:
        return result
    sub_fields = (spec or {}).get("fields") or {}
    linked_by_id = {rec.id: rec[FIELD] for rec in records.sudo()}
    for vals in result:
        current = vals.get(FIELD)
        linked = linked_by_id.get(vals.get("id"))
        if not isinstance(current, list) or not linked:
            continue
        if not sub_fields:
            # Pidieron solo los ids.
            shown = set(current)
            current.extend(i for i in linked.ids if i not in shown)
            continue
        shown = {item.get("id") for item in current if isinstance(item, dict)}
        for expedient in linked:
            if expedient.id in shown:
                continue
            item = dict.fromkeys(sub_fields, False)
            item.update({"id": expedient.id, "display_name": expedient.display_name})
            current.append(item)
    return result


def link_write(records, vals, write):
    """Escribe `vals` con `write(recs, vals)`; el vínculo, con sudo.

    El permiso sobre el documento se verifica con el usuario real: el sudo es
    solo para que la escritura del vínculo vea también los expedientes que
    el usuario no ve.
    """
    if FIELD not in vals or records.env.su:
        return write(records, vals)
    vals = dict(vals)
    commands = vals.pop(FIELD)
    records.check_access("write")
    res = write(records, vals) if vals else True
    write(records.sudo(), {FIELD: commands})
    return res
