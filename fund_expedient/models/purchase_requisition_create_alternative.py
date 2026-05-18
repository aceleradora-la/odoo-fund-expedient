# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def _get_origin_purchase_order(self):
        """RFQ origen del wizard (Odoo 18 usa origin_po_id, no active_ids del contexto)."""
        self.ensure_one()
        if getattr(self, "origin_po_id", False):
            return self.origin_po_id
        ctx = self.env.context
        po_id = ctx.get("default_origin_po_id") or ctx.get("origin_po_id")
        if po_id:
            return self.env["purchase.order"].browse(po_id).exists()
        active_id = ctx.get("active_id")
        if active_id and ctx.get("active_model") == "purchase.order":
            return self.env["purchase.order"].browse(active_id).exists()
        return self.env["purchase.order"]

    def _get_new_alternative_po(self, origin_po, before_alt_ids, res):
        """Detecta la RFQ alternativa recién creada para una RFQ origen concreta."""
        PurchaseOrder = self.env["purchase.order"]
        if isinstance(res, dict) and res.get("res_model") == "purchase.order":
            rid = res.get("res_id")
            if rid:
                po = PurchaseOrder.browse(rid).exists()
                if po and po.id != origin_po.id:
                    return po
            rids = res.get("res_ids")
            if isinstance(rids, (list, tuple)) and rids:
                pos = PurchaseOrder.browse(rids).exists()
                pos = pos.filtered(lambda p: p.id != origin_po.id)
                if pos:
                    return pos[:1]

        origin_po.invalidate_recordset(["alternative_po_ids", "purchase_group_id", "order_line"])
        if hasattr(origin_po, "alternative_po_ids"):
            new_alts = origin_po.alternative_po_ids.filtered(
                lambda p: p.id not in before_alt_ids and p.id != origin_po.id
            )
            if new_alts:
                return new_alts.sorted(key=lambda p: p.id)[-1:]

        if hasattr(origin_po, "purchase_group_id") and origin_po.purchase_group_id:
            group_pos = origin_po.purchase_group_id.order_ids
            new_in_group = group_pos.filtered(
                lambda p: p.id not in before_alt_ids and p.id != origin_po.id
            )
            if new_in_group:
                return new_in_group.sorted(key=lambda p: p.id)[-1:]

        return PurchaseOrder

    def action_create_alternative(self):
        """Crear alternativas y copiar expedientes desde la RFQ origen del wizard."""
        origin_po = self._get_origin_purchase_order()
        before_alt_ids = set()
        if origin_po and hasattr(origin_po, "alternative_po_ids"):
            before_alt_ids = set(origin_po.alternative_po_ids.ids)
        if origin_po and hasattr(origin_po, "purchase_group_id") and origin_po.purchase_group_id:
            before_alt_ids |= set(origin_po.purchase_group_id.order_ids.ids)

        res = super().action_create_alternative()

        if not origin_po or not origin_po.expedient_ids:
            return res

        new_alt = self._get_new_alternative_po(origin_po, before_alt_ids, res)
        if not new_alt:
            return res

        new_alt.write({"expedient_ids": [(6, 0, origin_po.expedient_ids.ids)]})

        orig_lines = origin_po.order_line.sorted(key=lambda l: (l.sequence, l.id))
        for alt in new_alt:
            alt.invalidate_recordset(["order_line"])
            alt_lines = alt.order_line.sorted(key=lambda l: (l.sequence, l.id))
            for ol, al in zip(orig_lines, alt_lines):
                if ol.name and al.name != ol.name:
                    try:
                        al.write({"name": ol.name})
                    except Exception:
                        pass

        return res
