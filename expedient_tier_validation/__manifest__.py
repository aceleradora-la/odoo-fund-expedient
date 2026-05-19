# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Expedientes - Validación por niveles",
    "summary": "Extiende los expedientes con un proceso de validación por niveles (tier validation).",
    "version": "18.0.2.8",
    "category": "Administration",
    "website": "",
    "author": "",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "fund_expedient",
        "base_tier_validation",
    ],
    "data": [
        "views/fund_expedient_views.xml",
        "views/fund_expedient_spend_request_views.xml",
        "views/fund_expedient_disposition_views.xml",
        "views/fund_expedient_resolution_views.xml",
        "templates/tier_validation_templates.xml",
    ],
}
