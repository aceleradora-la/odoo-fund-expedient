# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

PDF = base64.b64encode(b"%PDF-1.4 disposicion firmada")


@tagged("post_install", "-at_install")
class TestTypeMaxAndRelaunch(TransactionCase):
    """Tope por tipo, cierre sin Disposición de Odoo y expediente nuevo.

    Caso de la Compulsa abreviada (tope 4.000 UF): si el estimado supera el
    tope no se certifican fondos (hay que cambiar el tipo); si lo supera la
    oferta, se declara fracasada y se inicia una Licitación vinculada.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        Stage = cls.env["fund.expedient.stage"]
        cls.st_req = Stage.create({"name": "T Requerimiento", "state_type": "draft"})
        cls.st_prev = Stage.create(
            {
                "name": "T Certifica fondos",
                "state_type": "in_progress",
                "spend_request_mode": "preventiva",
            }
        )
        cls.st_final = Stage.create(
            {
                "name": "T Afectación definitiva",
                "state_type": "in_progress",
                "spend_request_mode": "final",
            }
        )
        cls.st_contract = Stage.create({"name": "T Contrato", "state_type": "approved"})
        cls.fracasado = cls.env.ref("fund_expedient.disposition_type_fracasado")
        cls.st_failed = Stage.create(
            {
                "name": "T Declarar fracasado",
                "state_type": "no_award",
                "final_outcome_type_id": cls.fracasado.id,
            }
        )
        currency = cls.env.company.currency_id
        Type = cls.env["fund.expedient.type"]
        cls.compulsa = Type.create(
            {
                "name": "T Compulsa",
                "approval_currency_id": currency.id,
                "max_amount_unit": 4000.0,
                "stage_assign_ids": [
                    Command.create(
                        {"stage_id": cls.st_req.id, "sequence": 1, "allow_edit_type_id": True}
                    ),
                    Command.create({"stage_id": cls.st_prev.id, "sequence": 2}),
                    Command.create({"stage_id": cls.st_final.id, "sequence": 3}),
                    Command.create(
                        {"stage_id": cls.st_contract.id, "sequence": 4, "is_final_stage": True}
                    ),
                    Command.create({"stage_id": cls.st_failed.id, "sequence": 5}),
                ],
            }
        )
        cls.licitacion = Type.create(
            {
                "name": "T Licitación",
                "approval_currency_id": currency.id,
                "stage_assign_ids": [
                    Command.create({"stage_id": cls.st_req.id, "sequence": 1}),
                    Command.create({"stage_id": cls.st_prev.id, "sequence": 2}),
                ],
            }
        )
        cls.requestor = cls.env["hr.employee"].create({"name": "T Solicitante"})
        cls.spec_type = cls.env.ref("fund_expedient.document_type_technical_spec")
        cls.dispo_type = cls.env["fund.expedient.document.type"].create(
            {"name": "T Disposición firmada"}
        )

    def _expedient(self, amount):
        return self.env["fund.expedient"].create(
            {
                "type_id": self.compulsa.id,
                "requestor_id": self.requestor.id,
                "contract_object": "Compra de equipamiento",
                "amount_estimated_manual": amount,
            }
        )

    def _go_to(self, expedient, stage):
        expedient.with_context(
            skip_validation_check=True,
            skip_spend_request_check=True,
            skip_document_check=True,
            skip_disposition_check=True,
            skip_resolution_check=True,
            skip_notification_check=True,
        ).write({"stage_id": stage.id})

    def test_warning_and_block_preventiva(self):
        expedient = self._expedient(4500.0)
        self.assertIn("supera el monto máximo", expedient.type_max_amount_warning)
        self._go_to(expedient, self.st_prev)
        with self.assertRaisesRegex(UserError, "Cambie el tipo de expediente"):
            expedient.action_create_spend_request_initial()

    def test_under_limit_generates_preventiva(self):
        expedient = self._expedient(3500.0)
        self.assertFalse(expedient.type_max_amount_warning)
        self._go_to(expedient, self.st_prev)
        expedient.action_create_spend_request_initial()
        # Con expedient_tier_validation y sin niveles configurados se aprueba sola.
        self.assertIn(expedient.spend_request_ids.preventiva_state, ("generated", "approved"))

    def test_type_change_clears_warning(self):
        expedient = self._expedient(4500.0)
        expedient.write({"type_id": self.licitacion.id})
        self.assertFalse(expedient.type_max_amount_warning)

    def test_offer_over_limit_blocks_definitiva(self):
        expedient = self._expedient(3500.0)
        expedient.amount_estimated_confirmed_manual = 4800.0
        self._go_to(expedient, self.st_final)
        with self.assertRaisesRegex(UserError, "Declare el expediente fracasado"):
            expedient.action_create_spend_request_final()

    def _declare_failed(self, expedient):
        wizard = self.env["fund.expedient.outcome.wizard"].create(
            {
                "expedient_id": expedient.id,
                "disposition_type_id": self.fracasado.id,
                "reference": "DISPO-123/2026",
                "document_type_id": self.dispo_type.id,
                "file_data": PDF,
                "file_name": "dispo.pdf",
            }
        )
        wizard.action_confirm()

    def test_declare_failed_with_uploaded_disposition(self):
        expedient = self._expedient(3500.0)
        self._go_to(expedient, self.st_final)
        self.assertTrue(expedient.can_declare_outcome)
        self._declare_failed(expedient)
        self.assertEqual(expedient.stage_id, self.st_failed)
        self.assertEqual(expedient.state, "no_award")
        doc = expedient.document_ids.filtered(lambda d: d.document_type_id == self.dispo_type)
        self.assertEqual(doc.stage_id, self.st_final, "Queda en la etapa donde se declaró")
        self.assertIn("DISPO-123/2026", doc.name)
        self.assertFalse(expedient.disposition_ids, "No se crea la Disposición de Odoo")
        self.assertFalse(expedient.can_declare_outcome)

    def test_declare_without_outcome_stage_fails(self):
        expedient = self.env["fund.expedient"].create(
            {
                "type_id": self.licitacion.id,
                "requestor_id": self.requestor.id,
                "contract_object": "Sin etapa de cierre",
            }
        )
        self.assertFalse(expedient.can_declare_outcome)
        with self.assertRaisesRegex(UserError, "no tiene una etapa de cierre"):
            expedient._declare_outcome(self.fracasado, {"name": "x"}, "R-1")

    def test_relaunch_as_licitacion(self):
        expedient = self._expedient(0.0)
        expedient.write({"amount_estimated_manual": 0.0})
        self.env["fund.expedient.line"].create(
            {
                "expedient_id": expedient.id,
                "name": "Notebook",
                "product_qty": 2,
                "price_unit_estimated": 1800.0,
            }
        )
        Document = self.env["fund.expedient.document"]
        Document.create(
            {
                "expedient_id": expedient.id,
                "name": "Requerimiento",
                "file_data": PDF,
                "file_name": "req.pdf",
            }
        )
        self._go_to(expedient, self.st_final)
        Document.create(
            {
                "expedient_id": expedient.id,
                "name": "ET",
                "document_type_id": self.spec_type.id,
                "file_data": PDF,
                "file_name": "et.pdf",
            }
        )
        Document.create(
            {
                "expedient_id": expedient.id,
                "name": "Acta de apertura",
                "file_data": PDF,
                "file_name": "acta.pdf",
            }
        )
        expedient.line_ids.with_context(skip_final_amount_check=True).write(
            {"price_unit_final": 2500.0}
        )
        self._declare_failed(expedient)
        self.assertTrue(expedient.can_relaunch)

        wizard = self.env["fund.expedient.relaunch.wizard"].create(
            {"expedient_id": expedient.id, "type_id": self.licitacion.id}
        )
        action = wizard.action_confirm()
        new = self.env["fund.expedient"].browse(action["res_id"])

        self.assertEqual(new.type_id, self.licitacion)
        self.assertEqual(new.stage_id, self.st_req, "Arranca en la primera etapa")
        self.assertEqual(new.parent_id, expedient)
        self.assertNotEqual(new.number, expedient.number)
        self.assertFalse(new.number.startswith(expedient.number + "-"))
        self.assertEqual(new.requestor_id, self.requestor)
        self.assertEqual(new.contract_object, "Compra de equipamiento")
        self.assertEqual(new.line_ids.mapped("amount_estimated_line"), [3600.0])
        self.assertEqual(new.line_ids.mapped("price_unit_final"), [0.0])
        self.assertEqual(
            sorted(new.document_ids.mapped("name")),
            ["ET", "Requerimiento"],
            "Pasan el requerimiento y la ET; el acta y la disposición quedan",
        )
        self.assertEqual(new.document_ids.stage_id, self.st_req)
        self.assertFalse(new.spend_request_ids)

    def test_relaunch_only_from_no_award(self):
        expedient = self._expedient(1000.0)
        self.assertFalse(expedient.can_relaunch)
        with self.assertRaisesRegex(UserError, "cerrado sin adjudicar"):
            expedient._relaunch_as(self.licitacion)

    def test_relaunch_restricted_to_stage_users(self):
        group = self.env["res.groups"].create({"name": "T Compras"})
        self.compulsa.stage_assign_ids.filtered(
            lambda a: a.stage_id == self.st_failed
        ).group_ids = group
        expedient = self._expedient(1000.0)
        self._go_to(expedient, self.st_failed)
        outsider = new_test_user(
            self.env, login="t_relaunch_outsider", groups="fund_expedient.group_fund_expedient_user"
        )
        buyer = new_test_user(
            self.env,
            login="t_relaunch_buyer",
            groups="fund_expedient.group_fund_expedient_user",
        )
        buyer.groups_id = [Command.link(group.id)]
        # Seguidores: así los dos pueden leer el expediente (reglas de privacidad).
        expedient.message_subscribe(partner_ids=(outsider | buyer).partner_id.ids)
        self.assertFalse(expedient.with_user(outsider).can_relaunch)
        self.assertTrue(expedient.with_user(buyer).can_relaunch)
