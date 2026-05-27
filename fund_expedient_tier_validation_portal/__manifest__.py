# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Expedientes - Validación por niveles (Portal)",
    "summary": "Aprobaciones tier validation desde el portal web",
    "version": "18.0.1.0.0",
    "category": "Administration",
    "website": "https://aceleradora.la",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": True,
    "depends": [
        "fund_expedient_portal",
        "expedient_tier_validation",
    ],
    "data": [
        "security/fund_expedient_tier_portal_security.xml",
        "security/ir.model.access.csv",
        "views/portal_tier_templates.xml",
    ],
}
