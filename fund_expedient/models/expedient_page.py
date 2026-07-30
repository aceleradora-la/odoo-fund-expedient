# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ExpedientPage(models.Model):
    """Catálogo de solapas del expediente, para poder mostrarlas por etapa.

    Cada registro representa una pestaña del formulario. El `code` es el que
    identifica a la solapa en la vista (atributo `name` del `<page>`), así que
    los registros de datos NO deben cambiarlo: es el vínculo entre la
    configuración y el formulario.

    Las etapas del tipo de expediente eligen qué solapas se ven
    (`fund.expedient.type.stage.assign.visible_page_ids`). Una etapa sin
    solapas configuradas muestra todas, que es el comportamiento histórico.
    """

    _name = "fund.expedient.page"
    _description = "Solapa del Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Identificador técnico de la solapa en el formulario. No modificar.",
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Ya existe una solapa con ese código."),
    ]

    @api.model
    def _all_codes_token(self):
        """Todos los códigos en el formato delimitado que consumen las vistas."""
        codes = self.sudo().search([]).mapped("code")
        return _codes_token(codes)


def _codes_token(codes):
    """Arma «|a|b|c|»: los delimitadores evitan coincidencias parciales.

    Las vistas preguntan `'|lines|' not in visible_page_codes`, de modo que un
    código no puede confundirse con otro que lo contenga.
    """
    clean = [c for c in codes if c]
    return "|%s|" % "|".join(clean) if clean else "|"
