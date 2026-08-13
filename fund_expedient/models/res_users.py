# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResUsers(models.Model):
    """Datos del resumen periódico de pendientes.

    Son métodos (no campos) porque solo los consume la plantilla de correo del
    resumen: calcularlos como campos obligaría a computarlos en cada lectura de
    usuario, y el costo no es trivial.
    """

    _inherit = "res.users"

    def _fund_digest_expedients(self):
        """Expedientes en poder del usuario.

        Reutiliza el `search` de `holder_user_ids` (fund.expedient), que ya
        resuelve la regla completa: si hay una aprobación en curso el
        responsable son los aprobadores; si no, los asignados de la etapa.
        Se excluyen los cerrados para no llenar el resumen de ruido.
        """
        self.ensure_one()
        return (
            self.env["fund.expedient"]
            .sudo()
            .search(
                [
                    ("holder_user_ids", "in", self.id),
                    ("state", "not in", ("cancel", "no_award")),
                ],
                order="request_date desc, id desc",
            )
        )

    def _fund_digest_approvals(self):
        """Expedientes con una aprobación pendiente del usuario.

        Se apoya en `_search_ids_with_pending_approval`, que en el módulo base
        devuelve vacío y en `expedient_tier_validation` cubre tanto las
        validaciones del expediente como las de su Solicitud. Así el resumen
        funciona con o sin el módulo de aprobaciones instalado.
        """
        self.ensure_one()
        Expedient = self.env["fund.expedient"].sudo()
        _pending_all, pending_mine = Expedient._search_ids_with_pending_approval(self)
        if not pending_mine:
            return Expedient.browse()
        return Expedient.search(
            [
                ("id", "in", list(pending_mine)),
                ("state", "not in", ("cancel", "no_award")),
            ],
            order="request_date desc, id desc",
        )

    def _fund_digest_has_content(self):
        """True si hay algo que informar: no se mandan resúmenes vacíos."""
        self.ensure_one()
        return bool(self._fund_digest_expedients() or self._fund_digest_approvals())
