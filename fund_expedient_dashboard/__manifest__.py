# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Fundación - Expedientes: tableros",
    "summary": "Tableros de Expedientes en la app Tableros (Expedientes y Contrataciones)",
    "version": "18.0.1.1.0",
    "category": "Administration",
    "website": "https://aceleradora.la",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    # Módulo aparte para no hacer depender el núcleo de Expedientes de la app
    # Tableros: se instala solo cuando conviven las dos.
    "auto_install": True,
    # El tablero de Expedientes grafica validaciones (expedient_tier_validation)
    # y la ejecución presupuestaria (fund_expedient_account_budget).
    "depends": [
        "fund_expedient",
        "expedient_tier_validation",
        "fund_expedient_account_budget",
        "spreadsheet_dashboard",
    ],
    "data": [
        "data/dashboards.xml",
    ],
}
