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
        active_ids = self.env.context.get("active_ids") or []
        active_id = self.env.context.get("active_id")
        if not active_ids and active_id:
            active_ids = [active_id]

        originals = self.env["purchase.order"].browse(active_ids).exists()
        before_by_original = {}
        for po in originals:
            if hasattr(po, "alternative_po_ids"):
                before_by_original[po.id] = set(po.alternative_po_ids.ids)
            else:
                before_by_original[po.id] = set()

        res = super().action_create_alternative()

        for original_po in originals:
            if not original_po.expedient_ids:
                continue

            # 1) Detectar alternativas nuevas con before/after
            original_po.invalidate_recordset(["alternative_po_ids", "order_line"])
            new_alts = self.env["purchase.order"]
            if hasattr(original_po, "alternative_po_ids"):
                before_alt_ids = before_by_original.get(original_po.id, set())
                new_alts = original_po.alternative_po_ids.filtered(
                    lambda p: p.id not in before_alt_ids
                )

            # 2) Fallback: parsear retorno (último recurso)
            if not new_alts and isinstance(res, dict) and res.get("res_model") == "purchase.order":
                rid = res.get("res_id")
                if rid:
                    new_alts = self.env["purchase.order"].browse(rid).exists()
                if not new_alts:
                    rids = res.get("res_ids")
                    if isinstance(rids, (list, tuple)) and rids:
                        new_alts = self.env["purchase.order"].browse(rids).exists()
                if not new_alts and res.get("domain"):
                    new_alts = self.env["purchase.order"].search(res["domain"])

            if not new_alts:
                continue

            # Copiar expediente(s)
            new_alts.write({"expedient_ids": [(6, 0, original_po.expedient_ids.ids)]})

            # Copiar descripción extendida de líneas (campo name) hacia alternativas
            orig_lines = original_po.order_line.sorted(key=lambda l: (l.sequence, l.id))
            for alt in new_alts:
                alt.invalidate_recordset(["order_line"])
                alt_lines = alt.order_line.sorted(key=lambda l: (l.sequence, l.id))
                for ol, al in zip(orig_lines, alt_lines):
                    # Mantener también secciones/notas si existen
                    if ol.name and al.name != ol.name:
                        try:
                            al.write({"name": ol.name})
                        except Exception:
                            pass

        return res
