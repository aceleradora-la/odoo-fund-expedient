# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Fundación - Expedientes: ejecución presupuestaria",
    "summary": "Presupuesto de Contabilidad vs. comprometido y real de los expedientes, por cuenta analítica",
    "version": "18.0.1.0.1",
    "category": "Administration",
    "website": "https://aceleradora.la",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    # Se instala solo cuando conviven Expedientes y los Presupuestos de
    # Contabilidad: el reporte no tiene sentido sin uno de los dos.
    "auto_install": True,
    "depends": [
        "fund_expedient",
        "account_budget",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fund_expedient_budget_report_views.xml",
    ],
}
