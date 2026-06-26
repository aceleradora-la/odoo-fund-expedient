# Tableros (Spreadsheet Dashboards, Enterprise) — importación

Dos tableros, ambos calibrados al export real de tu instancia (`version` 22, `odooVersion` 12):

- `tablero_expedientes.json` — visión general (4 gráficos).
- `tablero_aprobaciones.json` — específico de aprobaciones (3 gráficos). **Requiere upgrade del
  módulo `expedient_tier_validation`** (ver más abajo).

El procedimiento de importación es el mismo para ambos (sección "Importar").

---

## Tablero de Expedientes (`tablero_expedientes.json`)

Contenido (`spreadsheet_data`) de un tablero de Odoo Spreadsheet, con **4 gráficos Odoo**
en una sola hoja, alimentados por los modelos de estos addons:

| Gráfico | Tipo | Modelo Odoo | Medida | Agrupado por |
|---|---|---|---|---|
| Expedientes por etapa | barras | `fund.expedient` | conteo (`__count`) | `stage_id` |
| Presupuesto por cuenta analítica | barras | `fund.budget.line` | `amount_total` | `analytic_account_id` |
| Solicitudes de gasto (definitiva) por mes | líneas | `fund.expedient.spend.request` | `amount_definitiva` | `date_definitiva:month` |
| Validaciones por estado | torta | `tier.review` | `approval_qty` | `status` |

Filtro global: **Período** (fecha, `this_year`), cableado por `fieldMatching` a `request_date`
(expedientes), `date_definitiva` (solicitudes de gasto) y `create_date` (validaciones).

> Calibrado al export real de tu instancia (`fundacionsadosky`): `version` 22 y **`odooVersion` 12**.
> La ausencia de `odooVersion` era la causa del error `Cannot read properties of undefined
> (reading 'map')` en `migrate10to11` — al faltar, o-spreadsheet corría migraciones viejas sobre
> estructuras inexistentes. Ahora coincide con tu build y no debería migrar nada.

## Importar

1. Activá el **modo desarrollador**.
2. App **Tableros** → entrá o creá un **Grupo de tableros**.
3. Creá un tablero desde una hoja de cálculo y, con modo desarrollador, **Archivo → Importar/Subir
   JSON** y elegí `tablero_expedientes.json`. (Alternativa: **Documentos → Nuevo → Subir** el JSON,
   abrirlo con Odoo Spreadsheet y **Insertar en tablero**.)
4. Verificá que los 4 gráficos muestren datos reales.

## Por qué gráficos y no pivots

Los gráficos Odoo (`odoo_bar`/`odoo_line`/`odoo_pie`) son **data sources autocontenidos** — la
misma estructura del gráfico de facturas que ya funciona en tu tablero de Contabilidad. Evitan la
fragilidad de los pivots hechos a mano (formato de `measures` y fórmulas `=ODOO.PIVOT`). Si más
adelante querés tablas pivote, lo más seguro es generarlas desde las **vistas pivot que ya existen**
en los módulos e **Insertar en hoja de cálculo** (te da el formato exacto de tu instancia):

- Expedientes: `fund_expedient/views/fund_expedient_views.xml:686`.
- Solicitudes de gasto: `fund_expedient/views/expedient_spend_request_views.xml:201`.
- Validaciones: `expedient_tier_validation/views/tier_my_approvals_views.xml:38`.

## Ajustes que quizás quieras hacer tras importar

- **Filtro de Compañía / Departamento:** se pueden agregar desde el panel de **Filtros** del tablero
  y mapear a `company_id` / `requestor_department_id`. (No se incluyeron por defecto para mantener el
  JSON mínimo y evitar mappings a campos que varíen entre modelos.)
- **Presupuesto comprometido/real:** en `fund.budget.line`, `committed_amount`/`real_amount`/
  `balance_amount` son **computados no almacenados** y no sirven como medida de gráfico. Por eso el
  panel usa `amount_total` (almacenado). Para ver comprometido/real, agregá un gráfico sobre
  **`fund.budget`** con sus totales almacenados `total_committed` / `total_real` / `total_balance`.
- **"Ver registros" desde un gráfico:** si querés el enlace a la vista, completá
  `chartOdooMenusReferences` con `{"<id_figura>": "<xmlid_de_menú>"}` (hoy está vacío).

---

## Tablero de Aprobaciones (`tablero_aprobaciones.json`)

Tres gráficos sobre `tier.review`, agrupados **por aprobador** (`done_by`):

| Gráfico | Tipo | Medida | Agrupado por | Filtro (domain) |
|---|---|---|---|---|
| Aprobaciones de expedientes por aprobador y etapa | barras apiladas | `approval_qty` | `done_by`, `stage_id` | `fund_record_type=expedient`, `status=approved` |
| Aprobaciones de Solicitudes de Gasto por aprobador y fase | barras apiladas | `approval_qty` | `done_by`, `spend_phase` | `fund_record_type=spend_request`, `status=approved` |
| Tiempo promedio de aprobación (días) por aprobador | barras | `approval_duration_days` (promedio) | `done_by` | `status=approved` |

Filtro global **Período** cableado a `reviewed_date` (fecha de validación) en los 3 gráficos.

### ⚠️ Requiere upgrade del módulo antes de importar

El gráfico de tiempo promedio usa un campo nuevo, **`approval_duration_days`**, agregado a
`tier.review` en `expedient_tier_validation/models/tier_review.py`. Es un `Float` **almacenado
computado** (`aggregator="avg"`) = días entre la creación de la revisión (cuando se solicita la
validación, `create_date`) y su aprobación (`reviewed_date`); solo se calcula para revisiones
`approved` (el resto queda en 0, por eso el gráfico filtra `status=approved`).

Pasos:

1. Desplegá el código actualizado y **actualizá el módulo** `expedient_tier_validation`
   (versión `18.0.4.7`). Al ser campo almacenado computado, se recalcula para las revisiones
   existentes en el upgrade.
2. Recién entonces importá `tablero_aprobaciones.json` (mismo procedimiento que el otro tablero).

> Nota sobre el tiempo: no existe en `base_tier_validation` un timestamp de "pendiente desde", así
> que se usa `create_date` como inicio. Si una revisión espera a tiers previos (`approve_sequence`),
> ese tiempo de espera queda incluido en la duración.

---

## Tablero de Tiempos de Pago (`tablero_pagos.json`)

Tres elementos sobre `account.move` (facturas de proveedor), midiendo **días hasta el pago**
(`payment_delay_days`, promedio). Todos filtran `move_type=in_invoice`, `state=posted`,
`payment_state in (paid, in_payment)`:

| Elemento | Tipo | Agrupado por | Detalle |
|---|---|---|---|
| Días promedio de pago por mes | gráfico de líneas | `invoice_date:month` | evolución mensual |
| Días promedio de pago por proveedor | **tabla pivote** (`=PIVOT(1)`) | `partner_id` (filas) | una fila por proveedor |
| Promedio general de días de pago | **tarjeta KPI** (`scorecard`) | — | valor del período + comparación |

Filtro global **Período** cableado a `invoice_date` (fecha de la factura) en los tres.

**Tarjeta KPI con comparación interanual.** El scorecard no lee directamente del modelo: toma su
valor (`keyValue`) y su línea base (`baseline`) de dos celdas auxiliares (`B45`/`B46`), cada una con
una fórmula `=PIVOT.VALUE(n, "payment_delay_days")`:

- Pivote `2` → `offset: 0` en el `fieldMatching` del período = **promedio del período seleccionado**.
- Pivote `3` → `offset: -1` = **mismo período anterior**. El `offset` se mide en la granularidad del
  filtro: si arriba elegís un año, `-1` es el año anterior; si elegís un mes, el mes anterior.

La tarjeta muestra la diferencia (`baselineMode: "difference"`); como menos días es mejor, se colorea
**verde a la baja** (`baselineColorDown`) y **rojo al alza** (`baselineColorUp`). Las celdas `B45`/`B46`
quedan detrás de la tarjeta (no molestan); si querés, podés moverlas a otra hoja.

> ⚠️ La tabla pivote y la tarjeta KPI son los elementos **hechos a mano** del JSON (el resto son
> gráficos Odoo autocontenidos). Si tras importar la tabla o el KPI no renderizan en tu build, la vía
> infalible es generarlos desde la UI: para la tabla, abrí **Facturas de proveedor → vista Pivote**,
> poné la medida *Días hasta el pago* y agrupá filas por *Proveedor*, y **Insertar en hoja de cálculo**;
> para el KPI, **Insertar → Gráfico → Scorecard** apuntando a las celdas `B45`/`B46`. Eso genera el
> formato exacto de tu instancia.

### ⚠️ Requiere upgrade del módulo antes de importar

El tablero usa dos campos nuevos en `account.move`
(`fund_expedient/models/account_move.py`), agregados en `fund_expedient` versión **`18.0.4.10`**:

- **`payment_delay_days`** — `Float` **almacenado computado** (`aggregator="avg"`) = días entre
  `invoice_date` y la fecha en que la factura quedó totalmente pagada. Solo se calcula para facturas
  de proveedor (`in_invoice`) con `payment_state` en `paid`/`in_payment`; el resto queda en 0 (por eso
  los gráficos filtran esos estados, para no sesgar el promedio con ceros).
- **`payment_date`** — `Date` almacenado computado = fecha del último asiento conciliado contra la
  línea a pagar (el momento en que se completó el pago). Visible (solo lectura) en el formulario de la
  factura de proveedor.

Pasos:

1. Desplegá el código actualizado y **actualizá el módulo** `fund_expedient` (versión `18.0.4.10`).
   El `post_init_hook` fuerza el **backfill** de `payment_date`/`payment_delay_days` sobre las facturas
   de proveedor existentes (Odoo no recalcula de forma confiable campos computados almacenados que
   dependen de la conciliación al crearse la columna; por eso un primer intento dejaba el tablero
   vacío con todo en 0).
2. Recién entonces importá `tablero_pagos.json` (mismo procedimiento que los otros tableros).

> Nota sobre la fecha de pago: se toma de `account.partial.reconcile.max_date` de las conciliaciones
> sobre la línea a pagar (la fecha más tardía entre factura y pago). Si una factura se paga en varias
> cuotas, se usa la fecha de la última. Las facturas con conciliación legacy o saldadas con notas de
> crédito (`reversed`) no se consideran "pagadas" a estos efectos.

---

## Si migrás a Odoo 19

Reexportá un tablero cualquiera desde la instancia 19 (**Archivo → Download as JSON**) para conocer
su `version`/`odooVersion`, y copiá esos dos valores en este archivo. Los nombres de modelos y campos
de estos addons no cambian con la migración, así que las medidas y dimensiones siguen válidas.
