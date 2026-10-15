# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_project_rel",
        "project_id",
        "expedient_id",
        string="Expedientes",
    )
    expedient_count = fields.Integer(
        compute="_compute_expedient_count",
        string="Nº Expedientes",
    )

    def _compute_expedient_count(self):
        for rec in self:
            rec.expedient_count = len(rec.expedient_ids)

    def action_view_expedients(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fund_expedient.action_fund_expedient"
        )
        action["domain"] = [("id", "in", self.expedient_ids.ids)]
        action["context"] = {"default_project_ids": [(4, self.id)]}
        return action
