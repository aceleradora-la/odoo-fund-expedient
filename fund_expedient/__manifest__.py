# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Fundación - Expedientes",
    "summary": "Gestión de expedientes con etapas, partidas presupuestarias y relaciones con compras y proyectos",
    "version": "19.0.1.0.0",
    "category": "Administration",
    "website": "",
    "author": "",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "mail",
        "hr",
        "purchase",
        "project",
    ],
    "data": [
        "security/fund_expedient_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/expedient_stage_data.xml",
        "data/expedient_encuadre_data.xml",
        "data/budget_position_category_data.xml",
        "views/budget_position_views.xml",
        "views/expedient_stage_views.xml",
        "views/expedient_encuadre_views.xml",
        "views/fund_expedient_views.xml",
        "views/purchase_order_views.xml",
        "views/project_views.xml",
        "views/fund_expedient_menus.xml",
    ],
}
