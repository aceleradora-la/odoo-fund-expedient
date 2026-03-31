# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FundExpedientDocument(models.Model):
    _name = "fund.expedient.document"
    _description = "Documento por etapa del expediente"
    _order = "sequence, id"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string="Documento",
        required=True,
    )
    delivered = fields.Boolean(string="Entregado")
    notes = fields.Text(string="Observaciones")
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa origen",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )
