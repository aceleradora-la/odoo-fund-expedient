# Odoo - Expedientes para Fundación

Módulos de Odoo para la gestión de expedientes en una fundación: expedientes con etapas, cuentas analíticas, relación con compras y proyectos, y validación por niveles.

## Ramas

| Rama   | Versión Odoo | Manifest      |
|--------|--------------|---------------|
| **18.0** | Odoo 18      | 18.0.1.0   |
| **19.0** | Odoo 19      | 19.0.1.0   |

Clonar o descargar la rama que coincida con tu versión de Odoo.

## Módulos

| Módulo | Descripción |
|--------|-------------|
| **fund_expedient** | Expedientes, etapas, cuentas analíticas, encuadres, relación con Purchase y Project. |
| **expedient_tier_validation** | Validación por niveles (tier validation) sobre expedientes. Requiere [base_tier_validation](https://github.com/OCA/server-ux) (OCA). |

## Instalación

1. Añadir esta ruta como directorio de addons en Odoo (solo la ruta que contiene `fund_expedient` y `expedient_tier_validation`).
2. Actualizar lista de aplicaciones.
3. Instalar **Fundación - Expedientes**.
4. Opcional: instalar **base_tier_validation** (OCA server-ux, rama según tu Odoo) y **Expedientes - Validación por niveles**.

## Dependencias Odoo

- **fund_expedient**: `mail`, `hr`, `purchase`, `project`
- **expedient_tier_validation**: `fund_expedient`, `base_tier_validation`

## Licencia

AGPL-3.0 o posterior
