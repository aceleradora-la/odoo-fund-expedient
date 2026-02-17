# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    expedient_ids = fields.One2many(
        "fund.expedient",
        "project_id",
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
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {"default_project_id": self.id}
        return action
