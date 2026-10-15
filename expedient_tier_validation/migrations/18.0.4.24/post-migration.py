# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Los aprobadores de aprobaciones ya pedidas pasan a ser participantes.

Desde esta versión, al pedirse una aprobación los aprobadores se suman a los
participantes del expediente y como seguidores. Para las aprobaciones que ya
existían: se los suma a todos como participantes y, como en fund_expedient
18.0.19.0, se los suscribe solo en los expedientes abiertos.
"""

from odoo import SUPERUSER_ID, api

FUND_MODELS = (
    "fund.expedient",
    "fund.expedient.spend.request",
    "fund.expedient.disposition",
    "fund.expedient.resolution",
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    reviews = env["tier.review"].search([("model", "in", FUND_MODELS)])
    reviews.with_context(fund_participants_no_subscribe=True)._record_fund_participants()
    expedients = env["fund.expedient"].with_context(active_test=False).search(
        [("state", "not in", ("done", "no_award", "cancel"))]
    )
    for expedient in expedients:
        partners = expedient.participant_user_ids.partner_id
        if partners:
            expedient.message_subscribe(partner_ids=partners.ids)
