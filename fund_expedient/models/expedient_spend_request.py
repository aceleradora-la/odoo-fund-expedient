# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FundExpedientSpendRequest(models.Model):
    _name = "fund.expedient.spend.request"
    _description = "Solicitud de Gasto"
    _order = "id desc"
    _rec_name = "display_name"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="expedient_id.company_id", store=True)
    currency_id = fields.Many2one(related="expedient_id.currency_id", store=True, readonly=True)
    approval_currency_id = fields.Many2one(
        related="expedient_id.approval_currency_id", store=True, readonly=True
    )

    initial_number = fields.Char(
        string="Número (Inicial)",
        readonly=True,
        index=True,
        copy=False,
        default="/",
    )
    initial_date = fields.Date(string="Fecha (Inicial)")
    initial_amount = fields.Monetary(
        string="Importe (Inicial)",
        currency_field="currency_id",
        readonly=True,
    )
    initial_amount_unit = fields.Monetary(
        string="Importe (Inicial, moneda tipo)",
        currency_field="approval_currency_id",
        readonly=True,
    )

    final_number = fields.Char(
        string="Número (Definitiva)",
        readonly=True,
        index=True,
        copy=False,
        default="/",
    )
    final_date = fields.Date(string="Fecha (Definitiva)")
    final_amount_confirmed = fields.Monetary(
        string="Importe confirmado (Definitiva)",
        currency_field="currency_id",
        readonly=True,
    )
    final_amount_confirmed_unit = fields.Monetary(
        string="Importe confirmado (Definitiva, moneda tipo)",
        currency_field="approval_currency_id",
        readonly=True,
    )

    line_ids = fields.One2many(
        "fund.expedient.spend.request.line",
        "spend_request_id",
        string="Líneas",
        copy=False,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("expedient_id.number", "initial_number", "final_number")
    def _compute_display_name(self):
        for rec in self:
            exp = rec.expedient_id.number if rec.expedient_id and rec.expedient_id.number else ""
            ini = rec.initial_number if rec.initial_number and rec.initial_number != "/" else ""
            fin = rec.final_number if rec.final_number and rec.final_number != "/" else ""
            parts = [p for p in [ini, fin] if p]
            label = " / ".join(parts) if parts else ""
            rec.display_name = f"SG {exp} {label}".strip() if exp or label else "Solicitud de Gasto"

    _sql_constraints = [
        (
            "expedient_unique",
            "unique(expedient_id)",
            "Ya existe una Solicitud de Gasto para este expediente.",
        )
    ]

    def _next_number(self, code):
        self.ensure_one()
        seq_env = self.env["ir.sequence"].with_company(self.company_id)
        return seq_env.next_by_code(code) or "/"

    def action_generate_initial(self):
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "initial":
            raise UserError(
                _("La etapa actual no permite crear Solicitud de Gasto inicial.")
            )
        if not self.initial_number or self.initial_number == "/":
            self.initial_number = self._next_number("fund.expedient.spend.request.initial")
        if not self.initial_date:
            self.initial_date = fields.Date.context_today(self)
        self.initial_amount = exp.amount_estimated or 0.0
        self.initial_amount_unit = exp.amount_estimated_unit or 0.0

        # Snapshot de líneas del expediente
        self.line_ids.unlink()
        lines_vals = []
        for line in exp.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            lines_vals.append(
                {
                    "sequence": line.sequence,
                    "display_type": line.display_type,
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "product_qty": line.product_qty,
                    "product_uom_id": line.product_uom_id.id,
                }
            )
        self.line_ids = [(0, 0, v) for v in lines_vals]
        return True

    def action_generate_final(self):
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "final":
            raise UserError(
                _("La etapa actual no permite crear Solicitud de Gasto definitiva.")
            )
        if not self.initial_number or self.initial_number == "/":
            raise UserError(_("Primero debe existir la Solicitud de Gasto inicial."))
        if not self.line_ids:
            raise UserError(_("La Solicitud de Gasto inicial no tiene líneas."))

        if not self.final_number or self.final_number == "/":
            self.final_number = self._next_number("fund.expedient.spend.request.final")
        if not self.final_date:
            self.final_date = fields.Date.context_today(self)

        self.final_amount_confirmed = exp.amount_estimated_confirmed or 0.0
        self.final_amount_confirmed_unit = exp.amount_estimated_confirmed_unit or 0.0
        return True


class FundExpedientSpendRequestLine(models.Model):
    _name = "fund.expedient.spend.request.line"
    _description = "Línea de Solicitud de Gasto"
    _order = "spend_request_id, sequence, id"

    spend_request_id = fields.Many2one(
        "fund.expedient.spend.request",
        string="Solicitud de Gasto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    display_type = fields.Selection(
        [("line_section", "Sección"), ("line_note", "Nota")],
        default=False,
        help="Tipo de línea para secciones o notas.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto/Servicio",
        domain=[("purchase_ok", "=", True)],
        ondelete="restrict",
    )
    name = fields.Char(string="Descripción")
    product_qty = fields.Float(
        string="Cantidad",
        default=1.0,
        required=True,
        digits="Product Unit of Measure",
    )
    product_uom_id = fields.Many2one("uom.uom", string="Unidad")
    company_id = fields.Many2one(related="spend_request_id.company_id", store=True)

    @api.constrains("product_id", "name", "display_type")
    def _check_name_required(self):
        for line in self:
            if (
                not line.display_type
                and not line.product_id
                and not (line.name and str(line.name).strip())
            ):
                raise ValidationError(_("La descripción es obligatoria cuando no hay producto."))

