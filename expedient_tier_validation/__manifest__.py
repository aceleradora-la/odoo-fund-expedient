# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Expedientes - Validación por niveles",
    "summary": "Extiende los expedientes con un proceso de validación por niveles (tier validation).",
    "version": "18.0.1.0",
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
        "templates/tier_validation_templates.xml",
    ],
}
