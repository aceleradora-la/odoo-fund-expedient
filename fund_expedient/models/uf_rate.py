# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundUfRate(models.Model):
    _name = "fund.uf.rate"
    _description = "Cotización Unidad Retributiva"
    _order = "name desc"

    name = fields.Date(
        string="Fecha",
        required=True,
        index=True,
    )
    rate = fields.Float(
        string="Valor unidad (en moneda compañía)",
        digits=(16, 4),
        required=True,
        help="Valor de 1 unidad (UR o UF) expresada en la moneda de la compañía.",
    )
    unit_type = fields.Selection(
        [
            ("ur", "Unidad Retributiva (UR)"),
            ("uf", "Unidad Funcional (UF)"),
        ],
        string="Tipo de unidad",
        required=True,
        default="ur",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "company_date_unit_unique",
            "UNIQUE(company_id, name, unit_type)",
            "Ya existe una cotización para esta compañía, fecha y tipo de unidad.",
        ),
    ]

    @api.model
    def get_rate(self, company, date, unit_type="ur"):
        """Obtener la cotización vigente (UR o UF) para una compañía y fecha.
        Busca la cotización con fecha <= date, la más reciente.
        """
        if not company or not date:
            return 0.0
        rate = self.search(
            [
                ("company_id", "=", company.id if hasattr(company, "id") else company),
                ("name", "<=", date),
                ("unit_type", "=", unit_type),
            ],
            order="name desc",
            limit=1,
        )
        return rate.rate if rate else 0.0
