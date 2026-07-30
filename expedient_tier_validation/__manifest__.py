# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Expedientes - Validación por niveles",
    "summary": "Extiende los expedientes con un proceso de validación por niveles (tier validation).",
    "version": "18.0.4.11",
    "category": "Administration",
    "website": "https://aceleradora.la",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "fund_expedient",
        "base_tier_validation",
    ],
    "data": [
        "views/expedient_type_views.xml",
        "views/fund_expedient_views.xml",
        "views/fund_expedient_spend_request_views.xml",
        "views/fund_expedient_disposition_views.xml",
        "views/fund_expedient_resolution_views.xml",
        "views/tier_my_approvals_views.xml",
        "views/tier_my_approvals_menus.xml",
        "templates/tier_validation_templates.xml",
    ],
}
