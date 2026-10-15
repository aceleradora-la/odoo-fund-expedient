# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestPortalTier(TransactionCase):
    def test_tier_portal_model_inherit_pattern(self):
        for model_name in (
            "fund.expedient",
            "fund.expedient.spend.request",
            "fund.expedient.disposition",
            "fund.expedient.resolution",
        ):
            self.assertEqual(self.env[model_name]._name, model_name)

    def test_tier_portal_mixin_registered(self):
        self.assertTrue(
            self.env["tier.validation.portal.mixin"]._abstract
        )
