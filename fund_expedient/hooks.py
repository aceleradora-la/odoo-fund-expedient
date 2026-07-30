# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def _cursor_from_hook_arg(cr_or_env):
    """Odoo 18: `pre_init_hook` recibe `Environment`; en versiones anteriores recibía `cr`."""
    return cr_or_env.cr if hasattr(cr_or_env, "cr") else cr_or_env


def _env_from_hook_arg(cr_or_env):
    """Devuelve un `Environment` tanto si el hook recibió `Environment` (Odoo 18) como `cr`."""
    cr = _cursor_from_hook_arg(cr_or_env)
    if cr is cr_or_env:  # recibió un cursor crudo (Odoo < 18)
        return api.Environment(cr, SUPERUSER_ID, {})
    return cr_or_env  # ya es un Environment


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def pre_init_hook(cr_or_env):
    """Antes de cargar modelos: renombrar columnas legacy de Solicitud de Gasto (sin usar oldname en Odoo 18)."""
    cr = _cursor_from_hook_arg(cr_or_env)
    table = "fund_expedient_spend_request"
    if _table_exists(cr, table):
        renames = [
            ("initial_number", "number"),
            ("initial_date", "date_preventiva"),
            ("initial_amount", "amount_preventiva"),
            ("initial_amount_unit", "amount_preventiva_unit"),
            ("final_date", "date_definitiva"),
            ("final_amount_confirmed", "amount_definitiva"),
            ("final_amount_confirmed_unit", "amount_definitiva_unit"),
        ]
        for old_name, new_name in renames:
            if _column_exists(cr, table, old_name) and not _column_exists(cr, table, new_name):
                cr.execute(
                    'ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s";' % (table, old_name, new_name)
                )

    # ---- Limpieza definitiva de partida presupuestaria (deprecada) ----
    # La funcionalidad "Partida presupuestaria" fue reemplazada por "Cuenta
    # analítica" a nivel expediente y a nivel línea. Si instalaciones
    # previas dejaron tablas o columnas residuales, las eliminamos antes
    # de cargar el ORM para evitar errores de carga de modelos.
    _drop_legacy_budget_position(cr)


def _drop_legacy_budget_position(cr):
    """Elimina tablas/columnas residuales del feature de Partida presupuestaria.

    Caso especial: en `fund.expedient.type.stage.assign` la bandera
    `hide_budget_position_id` se reusaba como única forma de ocultar la
    *cuenta analítica* por etapa, por lo que su configuración debe
    PRESERVARSE bajo el nuevo nombre `hide_analytic_account_id`. Esto se
    resuelve con un RENAME (en lugar de DROP) cuando la nueva columna no
    existe todavía en la base.
    """
    # 1) Migración crítica: preservar la configuración de visibilidad
    #    "Ocultar Partida presupuestaria" → "Ocultar Cuenta analítica".
    assign_table = "fund_expedient_type_stage_assign"
    if _table_exists(cr, assign_table):
        old_col = "hide_budget_position_id"
        new_col = "hide_analytic_account_id"
        old_exists = _column_exists(cr, assign_table, old_col)
        new_exists = _column_exists(cr, assign_table, new_col)
        if old_exists and not new_exists:
            # Caso normal en upgrade: renombrar columna preservando datos.
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s";'
                % (assign_table, old_col, new_col)
            )
        elif old_exists and new_exists:
            # Caso defensivo (ambas columnas presentes): copiar TRUE de la
            # vieja a la nueva donde la nueva no esté seteada y luego dropear
            # la vieja para no dejar el campo huérfano.
            cr.execute(
                'UPDATE "%s" SET "%s" = TRUE '
                'WHERE COALESCE("%s", FALSE) = TRUE '
                '  AND COALESCE("%s", FALSE) = FALSE;'
                % (assign_table, new_col, old_col, new_col)
            )
            cr.execute('ALTER TABLE "%s" DROP COLUMN "%s";' % (assign_table, old_col))

    # 2) Columnas residuales sin migración (datos descartables porque la
    #    funcionalidad de partidas dejó de existir).
    legacy_columns = [
        ("fund_expedient", "budget_position_id"),
        ("account_move_line", "budget_position_id"),
        ("fund_budget_line", "budget_position_id"),
        ("fund_budget_adjustment_line", "budget_position_id"),
    ]
    for table, column in legacy_columns:
        if _table_exists(cr, table) and _column_exists(cr, table, column):
            cr.execute('ALTER TABLE "%s" DROP COLUMN IF EXISTS "%s";' % (table, column))

    # 3) Tablas residuales: borrar en orden inverso por dependencias FK.
    legacy_tables = [
        "fund_budget_position_report",
        "fund_budget_position",
        "fund_budget_position_category",
    ]
    for table in legacy_tables:
        if _table_exists(cr, table):
            cr.execute('DROP TABLE IF EXISTS "%s" CASCADE;' % table)
    # Vistas SQL residuales (el reporte era una vista).
    cr.execute('DROP VIEW IF EXISTS fund_budget_position_report CASCADE;')


def post_init_hook(cr_or_env, registry=None):
    """Migraciones ligeras al actualizar el módulo."""
    cr = _cursor_from_hook_arg(cr_or_env)
    cr.execute(
        """
        UPDATE fund_expedient_stage
           SET spend_request_mode = 'preventiva'
         WHERE spend_request_mode = 'initial'
        """
    )
    cr.execute(
        """
        UPDATE fund_expedient_spend_request
           SET spend_state = 'definitiva'
         WHERE final_number IS NOT NULL
           AND final_number != ''
           AND final_number != '/'
        """
    )
    cr.execute(
        """
        UPDATE fund_expedient_spend_request
           SET spend_state = 'preventiva'
         WHERE spend_state IS NULL
           AND number IS NOT NULL
           AND number != ''
           AND number != '/'
        """
    )
    # Totales estimados manuales cuando aún no hay líneas con importe
    cr.execute(
        """
        UPDATE fund_expedient fe
           SET amount_estimated_manual = amount_estimated
         WHERE amount_estimated IS NOT NULL
           AND (amount_estimated_manual IS NULL OR amount_estimated_manual = 0)
           AND NOT EXISTS (
               SELECT 1 FROM fund_expedient_line fl
                WHERE fl.expedient_id = fe.id
                  AND fl.display_type IS NULL
           )
        """
    )
    cr.execute(
        """
        UPDATE fund_expedient fe
           SET amount_estimated_confirmed_manual = amount_estimated_confirmed
         WHERE amount_estimated_confirmed IS NOT NULL
           AND (amount_estimated_confirmed_manual IS NULL OR amount_estimated_confirmed_manual = 0)
           AND NOT EXISTS (
               SELECT 1 FROM fund_expedient_line fl
                WHERE fl.expedient_id = fe.id
                  AND fl.display_type IS NULL
           )
        """
    )

    # Migración proveedor recomendado (legacy Many2one → Many2many)
    # Expediente: copiar recommended_supplier_id hacia tabla rel.
    cr.execute(
        """
        INSERT INTO fund_expedient_recommended_supplier_rel (expedient_id, partner_id)
        SELECT fe.id, fe.recommended_supplier_id
          FROM fund_expedient fe
         WHERE fe.recommended_supplier_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    # Líneas: copiar recommended_supplier_id hacia tabla rel.
    cr.execute(
        """
        INSERT INTO fund_expedient_line_recommended_supplier_rel (line_id, partner_id)
        SELECT fl.id, fl.recommended_supplier_id
          FROM fund_expedient_line fl
         WHERE fl.recommended_supplier_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # ----------------------------------------------------------------------
    # Backfill de campos `related` con `store=True`.
    #
    # Cuando se agrega un campo `related` con `store=True`, Odoo crea la
    # columna nueva pero NO recomputa los datos para los registros
    # existentes (sólo recalcula al escribir el registro). Eso provoca que
    # el "Sector requirente" / "Responsable del sector" aparezcan vacíos
    # en SGs ya creadas a pesar de estar bien definidos en el expediente.
    # Forzamos el rellenado vía SQL para evitar pedirle al usuario que
    # toque manualmente cada expediente/SG.
    # ----------------------------------------------------------------------

    # 1) Expediente: derivar departamento del empleado solicitante.
    cr.execute(
        """
        UPDATE fund_expedient fe
           SET requestor_department_id = he.department_id
          FROM hr_employee he
         WHERE fe.requestor_id = he.id
           AND he.department_id IS NOT NULL
           AND (fe.requestor_department_id IS NULL
                OR fe.requestor_department_id <> he.department_id)
        """
    )
    # 2) Expediente: derivar manager del departamento del solicitante.
    cr.execute(
        """
        UPDATE fund_expedient fe
           SET requestor_department_manager_id = hd.manager_id
          FROM hr_employee he
          JOIN hr_department hd ON hd.id = he.department_id
         WHERE fe.requestor_id = he.id
           AND hd.manager_id IS NOT NULL
           AND (fe.requestor_department_manager_id IS NULL
                OR fe.requestor_department_manager_id <> hd.manager_id)
        """
    )
    # 3) Solicitud de Gasto: heredar del expediente todos los campos
    #    `related` con store=True que se agregaron recientemente.
    cr.execute(
        """
        UPDATE fund_expedient_spend_request sg
           SET requestor_id = fe.requestor_id,
               requestor_department_id = fe.requestor_department_id,
               requestor_department_manager_id = fe.requestor_department_manager_id,
               contract_object = COALESCE(sg.contract_object, fe.contract_object),
               delivery_location = COALESCE(sg.delivery_location, fe.delivery_location)
          FROM fund_expedient fe
         WHERE sg.expedient_id = fe.id
           AND (
                sg.requestor_id IS DISTINCT FROM fe.requestor_id
             OR sg.requestor_department_id IS DISTINCT FROM fe.requestor_department_id
             OR sg.requestor_department_manager_id IS DISTINCT FROM fe.requestor_department_manager_id
             OR sg.contract_object IS NULL
             OR sg.delivery_location IS NULL
           )
        """
    )

    # Objeto de la contratación pasa a ser obligatorio: rellenar históricos vacíos.
    if _table_exists(cr, "fund_expedient") and _column_exists(cr, "fund_expedient", "contract_object"):
        cr.execute(
            """
            UPDATE fund_expedient
               SET contract_object = '(Completar objeto de la contratación)'
             WHERE contract_object IS NULL
                OR BTRIM(contract_object) = ''
            """
        )

    # ----------------------------------------------------------------------
    # Backfill de `payment_date` / `payment_delay_days` en facturas existentes.
    #
    # Son campos computados con `store=True` que dependen de la conciliación
    # (`account.partial.reconcile`). Al agregarlos, Odoo crea la columna pero
    # el recálculo inicial sobre registros ya conciliados no es confiable, así
    # que las facturas históricas quedan en NULL/0 y el tablero de tiempos de
    # pago sale vacío. Forzamos el recálculo vía ORM (no se puede por SQL puro
    # porque la lógica recorre las conciliaciones).
    # ----------------------------------------------------------------------
    env = _env_from_hook_arg(cr_or_env)
    AccountMove = env["account.move"]
    if "payment_delay_days" in AccountMove._fields:
        moves = AccountMove.search([("move_type", "=", "in_invoice")])
        if moves:
            moves._compute_payment_delay()
            moves.flush_recordset(["payment_date", "payment_delay_days"])

    # Vistas de etapas generadas por código: crearlas si faltan y reescribir el
    # arch cuando se agregan campos nuevos (p. ej. `final_outcome`).
    env["fund.expedient.stage"].init_expedient_stage_view()

    _migrate_document_flags_to_types(cr, env)
    _recompute_expedient_commercial_amounts(env)


def _migrate_document_flags_to_types(cr, env):
    """Migrar los booleanos de pliego al catálogo de tipos de documento.

    Antes, cada documento tenía `is_technical_spec` / `is_particular_conditions` y
    cada etapa del tipo exigía esos dos documentos con
    `require_technical_spec_document` / `require_particular_conditions_document`.
    Ahora ambas cosas se expresan con `fund.expedient.document.type`.

    Los campos viejos ya no existen en los modelos, pero sus columnas siguen en la
    base (Odoo no las borra), así que se leen por SQL. Las columnas se conservan
    por si hiciera falta revertir.
    """
    spec_type = env.ref("fund_expedient.document_type_technical_spec", raise_if_not_found=False)
    cond_type = env.ref(
        "fund_expedient.document_type_particular_conditions", raise_if_not_found=False
    )
    if not spec_type or not cond_type:
        return

    # 1) Documentos: asignar el tipo según la marca que tuvieran.
    #    Si un documento tuviera ambas marcas, gana especificación técnica
    #    (el ORDER BY del CASE lo resuelve al elegir un único tipo por fila).
    if _table_exists(cr, "fund_expedient_document") and _column_exists(
        cr, "fund_expedient_document", "is_technical_spec"
    ):
        cr.execute(
            """
            UPDATE fund_expedient_document
               SET document_type_id = CASE
                       WHEN is_technical_spec THEN %s
                       ELSE %s
                   END
             WHERE document_type_id IS NULL
               AND (is_technical_spec OR is_particular_conditions)
            """,
            (spec_type.id, cond_type.id),
        )

    # 2) Etapas del tipo de expediente: convertir cada booleano en una fila del M2M.
    if _table_exists(cr, "fund_expedient_type_stage_assign") and _column_exists(
        cr, "fund_expedient_type_stage_assign", "require_technical_spec_document"
    ):
        for column, doc_type in (
            ("require_technical_spec_document", spec_type),
            ("require_particular_conditions_document", cond_type),
        ):
            cr.execute(
                """
                INSERT INTO fund_expedient_stage_assign_doc_type_rel
                            (assign_id, document_type_id)
                SELECT a.id, %%s
                  FROM fund_expedient_type_stage_assign a
                 WHERE a.%s IS TRUE
                ON CONFLICT DO NOTHING
                """
                % column,
                (doc_type.id,),
            )


def _recompute_expedient_commercial_amounts(env):
    """Recalcular comprometido/real de todos los expedientes.

    Esos campos son `store=True` pero sin dependencias sobre OC ni facturas: se
    invalidan a mano (`_invalidate_commercial_computes`). Hasta ahora `account.move`
    no tenía hook en `create`, por lo que las facturas creadas ya vinculadas dejaban
    el total desactualizado (se veía como columna «Facturas reales» vacía). Este
    recálculo pone al día los datos existentes; el hook nuevo evita que se repita.
    """
    expedients = env["fund.expedient"].search([])
    if not expedients:
        return
    fields_to_refresh = [
        "amount_committed",
        "amount_real",
        "amount_committed_unit",
        "amount_real_unit",
    ]
    expedients.invalidate_recordset(fields_to_refresh)
    expedients.modified(fields_to_refresh)
    expedients.flush_recordset(fields_to_refresh)
