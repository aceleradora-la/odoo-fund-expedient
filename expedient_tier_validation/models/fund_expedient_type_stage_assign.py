# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ExpedientTypeStageAssign(models.Model):
    _inherit = "fund.expedient.type.stage.assign"

    auto_advance_on_tier_validated = fields.Boolean(
        string="Avanzar etapa al validar",
        help=(
            "Si está activo y la etapa tiene validación por niveles (tier validation), "
            "al completarse todas las aprobaciones de la etapa actual el expediente "
            "pasa automáticamente a la siguiente etapa (si cumple el resto de requisitos)."
        ),
    )
