# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Fundación - Expedientes (Portal)",
    "summary": "Acceso portal a expedientes: listado, detalle y avance de etapas",
    "version": "18.0.1.0.6",
    "category": "Administration",
    "website": "https://aceleradora.la",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "fund_expedient",
        "portal",
        "website",
        "account",
    ],
    "data": [
        "security/fund_expedient_portal_security.xml",
        "security/ir.model.access.csv",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "fund_expedient_portal/static/src/scss/portal_expedient.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
}
