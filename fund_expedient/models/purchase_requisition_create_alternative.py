# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def action_create_alternative(self):
        """Crear alternativas y copiar expedientes desde la RFQ original.

        El wizard estándar crea una o varias RFQs alternativas a partir de la RFQ activa.
        Como `expedient_ids` es un Many2many custom, lo replicamos explícitamente.
        """
        # Capturar RFQ original antes de crear alternativas
        active_id = self.env.context.get("active_id")
        original_po = self.env["purchase.order"].browse(active_id).exists() if active_id else self.env["purchase.order"]

        res = super().action_create_alternative()

        if not original_po or not original_po.expedient_ids:
            return res

        # Intentar recuperar alternativas creadas:
        # - algunas versiones retornan un act_window con domain res_id(s)
        # - fallback: usar relación alternative_po_ids del original
        alt_pos = self.env["purchase.order"]
        if isinstance(res, dict):
            if res.get("res_model") == "purchase.order" and res.get("res_id"):
                alt_pos = self.env["purchase.order"].browse(res["res_id"]).exists()
            elif res.get("res_model") == "purchase.order" and res.get("domain"):
                alt_pos = self.env["purchase.order"].search(res["domain"])
        if not alt_pos and hasattr(original_po, "alternative_po_ids"):
            alt_pos = original_po.alternative_po_ids

        if alt_pos:
            alt_pos.write({"expedient_ids": [(6, 0, original_po.expedient_ids.ids)]})

        return res

