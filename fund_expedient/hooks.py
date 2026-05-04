# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

def post_init_hook(cr, registry):
    """Migraciones ligeras al actualizar el módulo."""
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
