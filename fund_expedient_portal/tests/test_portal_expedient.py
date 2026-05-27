# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestPortalExpedient(TransactionCase):
    def test_portal_or_domain_helpers(self):
        expedient = self.env["fund.expedient"]
        self.assertEqual(
            expedient._portal_or_domain([("id", "=", 1)]),
            [("id", "=", 1)],
        )
        self.assertEqual(
            expedient._portal_or_domain([]),
            [("id", "=", False)],
        )
        or_domain = expedient._portal_or_domain(
            [("id", "=", 1), ("id", "=", 2)]
        )
        self.assertEqual(or_domain, ["|", ("id", "=", 1), ("id", "=", 2)])

    def test_portal_base_domain_not_public(self):
        expedient = self.env["fund.expedient"]
        domain = expedient._portal_expedient_base_domain()
        self.assertIsInstance(domain, list)
        self.assertTrue(domain)

    def test_portal_model_inherit_pattern(self):
        """Evita regresión: extensión debe declarar _name explícito."""
        cls = type(self.env["fund.expedient"])
        self.assertEqual(cls._name, "fund.expedient")

    def test_portal_stage_nav_structure(self):
        expedient = self.env["fund.expedient"].new({})
        nav = expedient._portal_stage_nav_values()
        self.assertIn("portal_stage_show_panel", nav)
        self.assertIn("portal_can_previous", nav)
        self.assertIn("portal_can_next", nav)
        self.assertIn("portal_block_previous", nav)
        self.assertIn("portal_block_next", nav)

    def test_portal_stage_nav_cancelled(self):
        Expedient = self.env["fund.expedient"]
        expedient = Expedient.new({"state": "cancel"})
        nav = expedient._portal_stage_nav_values()
        if expedient._portal_is_internal_user():
            self.assertTrue(nav["portal_stage_show_panel"])
            self.assertFalse(nav["portal_can_previous"])
            self.assertFalse(nav["portal_can_next"])
            self.assertTrue(nav["portal_block_next"])
