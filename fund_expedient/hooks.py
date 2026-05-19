# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def _cursor_from_hook_arg(cr_or_env):
    """Odoo 18: `pre_init_hook` recibe `Environment`; en versiones anteriores recibía `cr`."""
    return cr_or_env.cr if hasattr(cr_or_env, "cr") else cr_or_env


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
