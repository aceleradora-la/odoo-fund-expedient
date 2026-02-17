# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BudgetPosition(models.Model):
    _name = "fund.budget.position"
    _description = "Partida Presupuestaria"
    _parent_store = True
    _order = "code"
    _rec_names_search = ["name", "code"]

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    type = fields.Selection(
        selection=[("normal", "Normal"), ("view", "Vista")],
        required=True,
        default="normal",
    )
    budget_assignment_allowed = fields.Boolean(
        string="Permite asignación presupuestaria",
        default=False,
    )
    category_id = fields.Many2one(
        "fund.budget.position.category",
        string="Categoría",
    )
    parent_path = fields.Char(index=True)
    parent_id = fields.Many2one(
        "fund.budget.position",
        string="Padre",
        ondelete="cascade",
        domain=[("type", "=", "view")],
        context={"default_type": "view"},
    )
    child_ids = fields.One2many(
        "fund.budget.position",
        "parent_id",
        string="Hijas",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    sequence = fields.Integer(default=10)

    @api.constrains("child_ids", "type", "parent_id")
    def _check_type(self):
        for rec in self:
            if rec.child_ids and rec.type != "view":
                raise ValidationError(
                    _(
                        "No puede definir hijas en una partida con tipo "
                        "distinto de 'Vista'."
                    )
                )

    @api.constrains(
        "budget_assignment_allowed",
        "parent_id",
        "child_ids",
    )
    def _check_budget_assignment_allowed(self):
        for rec in self:
            if rec.budget_assignment_allowed:
                parents = rec._get_parent_assignment_positions()
                if parents:
                    raise ValidationError(
                        _(
                            "En una misma rama solo una partida puede tener "
                            "'Permite asignación presupuestaria'."
                        )
                children_allowed = self.search(
                    [
                        ("id", "child_of", rec.id),
                        ("id", "!=", rec.id),
                        ("budget_assignment_allowed", "=", True),
                    ]
                )
                if children_allowed:
                    raise ValidationError(
                        _(
                            "No puede activar 'Permite asignación presupuestaria' "
                            "en %(parent)s porque la partida hija %(child)s ya la tiene."
                        )
                        % {"parent": rec.name, "child": children_allowed[0].name}
                    )

    def _get_parent_assignment_positions(self):
        self.ensure_one()
        result = self.env["fund.budget.position"]
        parent = self.parent_id
        while parent:
            if parent.budget_assignment_allowed:
                result |= parent
            parent = parent.parent_id
        return result
