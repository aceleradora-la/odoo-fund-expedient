# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ExpedientDispositionType(models.Model):
    """Catálogo de tipos de disposición.

    Reemplaza a la lista fija (Adjudicación / Desierto / Sin efecto /
    Fracasado) para poder dar de alta tipos nuevos sin tocar código.

    El que decide si el expediente se cierra es el tipo, con
    `closes_expedient`. La etapa donde se cierra se resuelve apuntando a este
    mismo tipo desde `fund.expedient.stage.final_outcome_type_id`: así un tipo
    nuevo + su etapa de cierre alcanzan para tener un resultado nuevo, y cada
    tipo de expediente puede cerrar en la etapa que le corresponda.
    """

    _name = "fund.expedient.disposition.type"
    _description = "Tipo de Disposición"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Identificador técnico. Se usa para la migración de datos y para "
        "referenciar el tipo desde código; no conviene cambiarlo.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help="Desmarcar para dejar de ofrecerlo sin borrar las disposiciones que lo usan.",
    )
    closes_expedient = fields.Boolean(
        string="Cierra el expediente",
        help="Si está activo, al aplicar una disposición de este tipo el expediente "
        "se cierra en la etapa del flujo que tenga este mismo tipo como «Resultado "
        "final». Si no, el proceso continúa con las etapas siguientes.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Ya existe un tipo de disposición con ese código."),
    ]
