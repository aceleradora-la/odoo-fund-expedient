# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMyApprovalsPartner(TransactionCase):
    """Columna «Contacto / Proveedor» de Mis aprobaciones para expedientes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # En una copia de prod puede haber niveles sobre expedientes: no influyen acá.
        cls.env["tier.definition"].search([("model", "like", "fund.expedient")]).active = False
        stage = cls.env["fund.expedient.stage"].create(
            {"name": "T Pedido", "state_type": "draft"}
        )
        expedient_type = cls.env["fund.expedient.type"].create(
            {
                "name": "T Tipo",
                "approval_currency_id": cls.env.company.currency_id.id,
                "stage_assign_ids": [Command.create({"stage_id": stage.id, "sequence": 1})],
            }
        )
        Partner = cls.env["res.partner"]
        cls.recommended = Partner.create({"name": "T Recomendado SA", "is_company": True})
        cls.awarded = Partner.create({"name": "T Adjudicado SRL", "is_company": True})
        cls.expedient = cls.env["fund.expedient"].create(
            {
                "type_id": expedient_type.id,
                "requestor_id": cls.env["hr.employee"].create({"name": "T Solicitante"}).id,
                "contract_object": "Compra de prueba",
                "recommended_supplier_ids": [Command.set(cls.recommended.ids)],
            }
        )
        definition = cls.env["tier.definition"].create(
            {
                "name": "T Nivel",
                "model_id": cls.env["ir.model"]._get("fund.expedient").id,
                "review_type": "individual",
                "reviewer_id": cls.env.user.id,
                "active": False,
            }
        )
        cls.review = cls.env["tier.review"].create(
            {
                "model": "fund.expedient",
                "res_id": cls.expedient.id,
                "definition_id": definition.id,
                "status": "pending",
            }
        )

    def test_recommended_supplier_before_purchase(self):
        self.assertEqual(self.review.partner_names, "T Recomendado SA")

    def test_confirmed_purchase_order_wins(self):
        rfq = self.env["purchase.order"].create({"partner_id": self.awarded.id})
        # La revisión pendiente del test bloquea editar el expediente.
        self.expedient.with_context(skip_validation_check=True).purchase_order_ids = [
            Command.link(rfq.id)
        ]
        # Una solicitud de cotización sin confirmar no cambia nada.
        self.assertEqual(self.review.partner_names, "T Recomendado SA")
        rfq.write({"state": "purchase"})
        self.review.invalidate_recordset(["partner_names"])
        self.assertEqual(self.review.partner_names, "T Adjudicado SRL")

    def test_spend_request_uses_expedient(self):
        spend_request = self.env["fund.expedient.spend.request"].new(
            {"expedient_id": self.expedient.id}
        )
        self.assertEqual(spend_request._my_approvals_partners(), self.recommended)
