# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def action_create_alternative(self):
        """Crear alternativas y copiar expedientes desde la RFQ original.

        Las RFQs nuevas se detectan por diferencia en alternative_po_ids antes/después
        del wizard estándar (más robusto que parsear solo el dict de retorno).
        """
        active_id = self.env.context.get("active_id")
        original_po = (
            self.env["purchase.order"].browse(active_id).exists()
            if active_id
            else self.env["purchase.order"]
        )
        before_alt_ids = set()
        if original_po and hasattr(original_po, "alternative_po_ids"):
            before_alt_ids = set(original_po.alternative_po_ids.ids)

        res = super().action_create_alternative()

        if not original_po or not original_po.expedient_ids:
            return res

        original_po.invalidate_recordset(["alternative_po_ids"])
        new_alts = self.env["purchase.order"]
        if hasattr(original_po, "alternative_po_ids"):
            new_alts = original_po.alternative_po_ids.filtered(lambda p: p.id not in before_alt_ids)

        if not new_alts and isinstance(res, dict):
            if res.get("res_model") == "purchase.order":
                rid = res.get("res_id")
                if rid:
                    new_alts = self.env["purchase.order"].browse(rid).exists()
                if not new_alts:
                    rids = res.get("res_ids")
                    if isinstance(rids, (list, tuple)) and rids:
                        new_alts = self.env["purchase.order"].browse(rids).exists()
                if not new_alts and res.get("domain"):
                    dom = res["domain"]
                    new_alts = self.env["purchase.order"].search(dom)

        if new_alts:
            new_alts.write({"expedient_ids": [(6, 0, original_po.expedient_ids.ids)]})

        return res
