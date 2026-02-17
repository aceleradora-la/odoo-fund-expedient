# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class BudgetPositionCategory(models.Model):
    _name = "fund.budget.position.category"
    _description = "Categoría de Partida Presupuestaria"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
