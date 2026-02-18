# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundUfRate(models.Model):
    _name = "fund.uf.rate"
    _description = "Cotización Unidad Funcional"
    _order = "name desc"

    name = fields.Date(
        string="Fecha",
        required=True,
        index=True,
    )
    rate = fields.Float(
        string="Valor UF (en moneda compañía)",
        digits=(16, 4),
        required=True,
        help="Valor de 1 UF expresado en la moneda de la compañía.",
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
            "company_date_unique",
            "UNIQUE(company_id, name)",
            "Ya existe una cotización UF para esta compañía y fecha.",
        ),
    ]

    @api.model
    def get_rate(self, company, date):
        """Obtener la cotización UF vigente para una compañía y fecha.
        Busca la cotización con fecha <= date, la más reciente.
        """
        if not company or not date:
            return 0.0
        rate = self.search(
            [
                ("company_id", "=", company.id if hasattr(company, "id") else company),
                ("name", "<=", date),
            ],
            order="name desc",
            limit=1,
        )
        return rate.rate if rate else 0.0
