# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ExpedientDocumentType(models.Model):
    """Catálogo de tipos de documento del expediente.

    Reemplaza a las marcas fijas `is_technical_spec` / `is_particular_conditions`
    que antes vivían en cada documento: ahora esas dos características son
    atributos del *tipo*, y se pueden definir tantos tipos como haga falta.
    Las etapas del tipo de expediente exigen una lista de estos tipos
    (`fund.expedient.type.stage.assign.required_document_type_ids`).
    """

    _name = "fund.expedient.document.type"
    _description = "Tipo de Documento de Expediente"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help="Desmarcar para dejar de ofrecer este tipo sin borrar los documentos "
        "que ya lo usan.",
    )
    is_technical_spec = fields.Boolean(
        string="Integra la especificación técnica",
        help="Los documentos de este tipo forman parte de la especificación técnica "
        "del expediente. Al notificar a oferentes se adjuntan automáticamente al correo.",
    )
    is_particular_conditions = fields.Boolean(
        string="Contiene las condiciones particulares",
        help="Los documentos de este tipo contienen las condiciones particulares del "
        "pliego (plazos, garantías, formas de pago). Al notificar a oferentes se "
        "adjuntan automáticamente al correo.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )
