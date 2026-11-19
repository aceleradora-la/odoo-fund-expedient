# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ExpedientOutcomeWizard(models.TransientModel):
    """Declarar el expediente desierto, sin efecto o fracasado.

    Las disposiciones se firman por fuera de Odoo y se suben como documento:
    acá no se crea el registro de Disposición (que lleva numeración propia).
    Se sube la disposición firmada a la etapa actual y el expediente pasa a la
    etapa de cierre del resultado elegido.
    """

    _name = "fund.expedient.outcome.wizard"
    _description = "Declarar resultado del expediente"

    expedient_id = fields.Many2one("fund.expedient", required=True, readonly=True)
    disposition_type_id = fields.Many2one(
        "fund.expedient.disposition.type",
        string="Resultado",
        required=True,
        domain="[('closes_expedient', '=', True)]",
    )
    reference = fields.Char(
        string="Nº de disposición",
        required=True,
        help="Número de la disposición firmada por fuera de Odoo.",
    )
    document_type_id = fields.Many2one(
        "fund.expedient.document.type",
        string="Tipo de documento",
        required=True,
        default=lambda self: self._default_document_type(),
    )
    file_data = fields.Binary(string="Disposición firmada", required=True)
    file_name = fields.Char(string="Nombre del archivo")
    notes = fields.Text(string="Observaciones")

    @api.model
    def _default_document_type(self):
        return self.env["fund.expedient.document.type"].search(
            [("name", "ilike", "disposici")], limit=1
        )

    def action_confirm(self):
        self.ensure_one()
        expedient = self.expedient_id
        if not expedient.can_declare_outcome:
            raise UserError(
                _(
                    "Solo los usuarios asignados a la etapa actual pueden declarar el "
                    "resultado del expediente."
                )
            )
        expedient._declare_outcome(
            self.disposition_type_id,
            {
                "name": _(
                    "%(outcome)s - Disposición %(ref)s",
                    outcome=self.disposition_type_id.name,
                    ref=self.reference,
                ),
                "document_type_id": self.document_type_id.id,
                "file_data": self.file_data,
                "file_name": self.file_name,
                "notes": self.notes and "<p>%s</p>" % self.notes,
            },
            reference=self.reference,
        )
        return {"type": "ir.actions.act_window_close"}
