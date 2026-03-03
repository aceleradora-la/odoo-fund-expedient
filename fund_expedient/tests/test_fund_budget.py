# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestFundBudget(TransactionCase):
    """Casos de prueba: consistencia presupuesto, ajustes y jerarquía de partidas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Budget = cls.env["fund.budget"]
        cls.BudgetLine = cls.env["fund.budget.line"]
        cls.BudgetPosition = cls.env["fund.budget.position"]
        cls.BudgetAdjustment = cls.env["fund.budget.adjustment"]
        cls.Report = cls.env["fund.budget.position.report"]

    def test_budget_create_and_constraint_unique_position(self):
        """Presupuesto: una partida solo puede aparecer una vez por presupuesto."""
        budget = self.Budget.create({
            "name": "Presupuesto Test",
            "fiscalyear": "2025",
            "company_id": self.company.id,
        })
        position = self.BudgetPosition.search(
            [("company_id", "=", self.company.id), ("budget_assignment_allowed", "=", True)],
            limit=1,
        )
        if not position:
            self.skipTest("No hay partida con asignación permitida")
        self.BudgetLine.create({
            "budget_id": budget.id,
            "budget_position_id": position.id,
            "initial_amount": 1000.0,
        })
        with self.assertRaises(Exception):  # IntegrityError o ValidationError
            self.BudgetLine.create({
                "budget_id": budget.id,
                "budget_position_id": position.id,
                "initial_amount": 500.0,
            })

    def test_budget_totals_from_lines(self):
        """Totales del presupuesto coinciden con la suma de líneas."""
        budget = self.Budget.create({
            "name": "Presupuesto Totales",
            "fiscalyear": "2025",
            "company_id": self.company.id,
        })
        positions = self.BudgetPosition.search(
            [("company_id", "=", self.company.id), ("budget_assignment_allowed", "=", True)],
            limit=2,
        )
        if len(positions) < 2:
            self.skipTest("Se necesitan al menos 2 partidas")
        self.BudgetLine.create([
            {"budget_id": budget.id, "budget_position_id": positions[0].id, "initial_amount": 1000.0},
            {"budget_id": budget.id, "budget_position_id": positions[1].id, "initial_amount": 2000.0},
        ])
        budget.invalidate_recordset()
        self.assertEqual(budget.total_budget, 3000.0)

    def test_adjustment_post_updates_budget_line(self):
        """Ajuste publicado modifica el presupuesto vigente de la partida."""
        budget = self.Budget.create({
            "name": "Presupuesto Ajuste",
            "fiscalyear": "2025",
            "company_id": self.company.id,
        })
        position = self.BudgetPosition.search(
            [("company_id", "=", self.company.id), ("budget_assignment_allowed", "=", True)],
            limit=1,
        )
        if not position:
            self.skipTest("No hay partida con asignación permitida")
        line = self.BudgetLine.create({
            "budget_id": budget.id,
            "budget_position_id": position.id,
            "initial_amount": 1000.0,
        })
        adjustment = self.BudgetAdjustment.create({
            "name": "Ajuste +500",
            "budget_id": budget.id,
            "date": "2025-06-01",
            "line_ids": [(0, 0, {"budget_position_id": position.id, "amount": 500.0})],
        })
        adjustment.action_post()
        line.invalidate_recordset()
        self.assertEqual(line.amount_total, 1500.0)
        self.assertEqual(line.adjustment_amount, 500.0)

    def test_report_returns_rows_per_budget_position(self):
        """El reporte SQL devuelve una fila por (presupuesto, partida)."""
        budget = self.Budget.create({
            "name": "Presupuesto Report",
            "fiscalyear": "2025",
            "company_id": self.company.id,
        })
        position = self.BudgetPosition.search(
            [("company_id", "=", self.company.id), ("budget_assignment_allowed", "=", True)],
            limit=1,
        )
        if not position:
            self.skipTest("No hay partida con asignación permitida")
        self.BudgetLine.create({
            "budget_id": budget.id,
            "budget_position_id": position.id,
            "initial_amount": 500.0,
        })
        rows = self.Report.search([("budget_id", "=", budget.id)])
        self.assertGreaterEqual(len(rows), 1)
        row = self.Report.search([
            ("budget_id", "=", budget.id),
            ("budget_position_id", "=", position.id),
        ], limit=1)
        self.assertTrue(row)
        self.assertEqual(row.amount_budget, 500.0)
