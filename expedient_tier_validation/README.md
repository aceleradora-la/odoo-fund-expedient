# Expedientes - Validación por niveles

Extiende el módulo **Fundación - Expedientes** con validación por niveles (tier validation) usando [base_tier_validation](https://github.com/OCA/server-ux/tree/18.0/base_tier_validation).

## Características

- Los expedientes pasan a tener un flujo de aprobación por niveles.
- Estados considerados: Borrador, En progreso, Por aprobar (requieren validación) → Aprobado.
- Configuración de niveles en **Ajustes > Tier Validation** o desde las definiciones de validación del modelo `fund.expedient`.

## Dependencias

- fund_expedient
- base_tier_validation (OCA server-ux)

## Uso

1. Instalar **base_tier_validation** y **fund_expedient**.
2. Instalar **Expedientes - Validación por niveles**.
3. En Ajustes (o en el menú de Tier Definitions), configurar las definiciones de validación para el modelo **Expediente** (fund.expedient).
4. Al pasar un expediente a un estado "Por aprobar" o "Aprobado", se aplicará la validación configurada.

### Revisor = Solicitante del expediente

El modelo `fund.expedient` expone el campo técnico **Usuario solicitante** (`requestor_user_id`), relacionado con el empleado solicitante.

En la definición de nivel (**Tier Definition**), seleccione como **Reviewer field** el campo **Usuario solicitante** (`requestor_user_id`) si desea que apruebe quien figura como solicitante del expediente.

## Licencia

AGPL-3.0 o posterior
