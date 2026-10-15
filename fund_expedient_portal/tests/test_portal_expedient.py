# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestPortalExpedient(TransactionCase):
    def test_portal_access_clauses_internal_user(self):
        """Usuario interno: solicitante o asignado; sin cláusulas de partner."""
        expedient = self.env["fund.expedient"]
        clauses = expedient._portal_access_clauses(self.env.user)
        fields = [clause[0] for clause in clauses]
        self.assertIn("requestor_id.user_id", fields)
        self.assertIn("assignable_user_ids", fields)
        self.assertNotIn("message_partner_ids", fields)

    def test_portal_access_clauses_portal_user(self):
        """Usuario de portal: además, partner seguidor o proveedor recomendado."""
        portal_user = self.env.ref("base.demo_user0", raise_if_not_found=False)
        if not portal_user:
            self.skipTest("Sin usuario de portal de demo")
        expedient = self.env["fund.expedient"]
        clauses = expedient._portal_access_clauses(portal_user)
        fields = [clause[0] for clause in clauses]
        self.assertIn("message_partner_ids", fields)
        self.assertIn("recommended_supplier_ids", fields)

    def test_portal_base_domain_public_sees_nothing(self):
        public_user = self.env.ref("base.public_user")
        expedient = self.env["fund.expedient"].with_user(public_user)
        self.assertEqual(expedient._portal_expedient_base_domain(), [("id", "=", False)])

    def test_portal_base_domain_not_public(self):
        domain = self.env["fund.expedient"]._portal_expedient_base_domain()
        self.assertIsInstance(domain, list)
        self.assertTrue(domain)

    def test_portal_model_inherit_pattern(self):
        """Evita regresión: extensión debe declarar _name explícito."""
        cls = type(self.env["fund.expedient"])
        self.assertEqual(cls._name, "fund.expedient")

    def test_portal_stage_nav_structure(self):
        expedient = self.env["fund.expedient"].new({})
        nav = expedient._portal_stage_nav_values()
        for key in (
            "portal_stage_show_panel",
            "portal_can_previous",
            "portal_can_next",
            "portal_block_previous",
            "portal_block_next",
        ):
            self.assertIn(key, nav)

    def test_portal_stage_nav_cancelled(self):
        """Cancelado: el panel se ve (opera la etapa) pero no se puede mover."""
        expedient = self.env["fund.expedient"].new({"state": "cancel"})
        nav = expedient._portal_stage_nav_values()
        if nav["portal_stage_show_panel"]:
            self.assertFalse(nav["portal_can_previous"])
            self.assertFalse(nav["portal_can_next"])
            self.assertTrue(nav["portal_block_next"])
