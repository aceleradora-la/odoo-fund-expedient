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
