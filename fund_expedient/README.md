# Fundación - Expedientes

Módulo de Odoo 18 para la gestión de expedientes de una fundación.

## Características

- **Expedientes** con numeración por secuencia configurable.
- **Etapas** configurables (maestro de etapas) con orden y tipo de estado para flujo y validación.
- **Cuentas analíticas** asignadas al expediente y a cada línea, con plan analítico configurable por compañía.
- **Encuadres** configurables (ej. Compra Simple, Compulsa Abreviada, Licitación).
- Relación con **Solicitudes de cotización** (purchase.order): campo Expediente en compras e icono en expediente.
- Relación con **Proyectos** (project.project): campo Proyecto en expediente e icono en proyecto.
- Relación **expediente padre/hijos** (otros expedientes).
- Vistas **Lista** y **Kanban** (agrupado por etapa).
- **Monto máximo por tipo** (p. ej. Compulsa abreviada: 4.000 UF): cartel en el expediente cuando el
  total lo supera y bloqueo al generar la Solicitud. Con la preventiva hay que cambiar el tipo; con
  la definitiva, declarar el expediente fracasado.
- **Declarar resultado** (desierto, sin efecto, fracasado) subiendo la disposición firmada como
  documento, sin crear la Disposición de Odoo. El tipo necesita la etapa de cierre del resultado en
  sus asignaciones por etapa.
- **Iniciar nuevo expediente** desde uno cerrado sin adjudicar: elige el tipo (p. ej. Licitación),
  copia solicitante, objeto, cuenta analítica, líneas y documentos del requerimiento, y queda
  vinculado como expediente relacionado.

## Dependencias

- mail, hr, purchase, project

## Instalación

Añadir la ruta de los addons y actualizar la lista de aplicaciones. Instalar "Fundación - Expedientes".

## Configuración

- **Expedientes > Configuración > Numeración de expedientes**: editar la secuencia (prefijo, padding, etc.).
- **Expedientes > Configuración > Etapas de expediente**: definir etapas y tipo de estado (borrador, en progreso, por aprobar, aprobado, cancelado).
- **Contabilidad > Configuración > Cuentas analíticas**: definir las cuentas analíticas que se asignarán a los expedientes y a sus líneas.

## Licencia

AGPL-3.0 o posterior
