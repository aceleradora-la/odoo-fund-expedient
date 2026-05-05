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

    number = fields.Char(
        string="Número",
        readonly=True,
        index=True,
        copy=False,
        default="/",
    )
    spend_state = fields.Selection(
        [
            ("preventiva", "Preventiva"),
            ("definitiva", "Definitiva"),
        ],
        string="Estado",
        readonly=True,
        index=True,
    )
    date_preventiva = fields.Date(string="Fecha preventiva")
    amount_preventiva = fields.Monetary(
        string="Importe preventivo",
        currency_field="currency_id",
        readonly=True,
    )
    amount_preventiva_unit = fields.Monetary(
        string="Importe preventivo (moneda tipo)",
        currency_field="approval_currency_id",
        readonly=True,
    )

    date_definitiva = fields.Date(string="Fecha definitiva")
    amount_definitiva = fields.Monetary(
        string="Importe definitivo",
        currency_field="currency_id",
        readonly=True,
    )
    amount_definitiva_unit = fields.Monetary(
        string="Importe definitivo (moneda tipo)",
        currency_field="approval_currency_id",
        readonly=True,
    )
    # Conservado por compatibilidad con BD existente; no generar nuevos valores.
    final_number = fields.Char(
        string="Número definitiva (hist.)",
        readonly=True,
        copy=False,
        default="/",
    )

    line_ids = fields.One2many(
        "fund.expedient.spend.request.line",
        "spend_request_id",
        string="Líneas",
        copy=False,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("expedient_id.number", "number", "spend_state")
    def _compute_display_name(self):
        for rec in self:
            exp = rec.expedient_id.number if rec.expedient_id and rec.expedient_id.number else ""
            num = rec.number if rec.number and rec.number != "/" else ""
            state_lbl = ""
            if rec.spend_state == "preventiva":
                state_lbl = _("Preventiva")
            elif rec.spend_state == "definitiva":
                state_lbl = _("Definitiva")
            parts = [p for p in [num, state_lbl] if p]
            label = " · ".join(parts) if parts else ""
            rec.display_name = f"SG {exp} {label}".strip() if exp or label else _("Solicitud de Gasto")

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

    def action_generate_preventiva(self):
        """Genera número único y snapshot preventivo (antes SG inicial)."""
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "preventiva":
            raise UserError(_("La etapa actual no permite crear Solicitud de Gasto preventiva."))
        if not self.number or self.number == "/":
            self.number = self._next_number("fund.expedient.spend.request")
        self.spend_state = "preventiva"
        if not self.date_preventiva:
            self.date_preventiva = fields.Date.context_today(self)
        self.amount_preventiva = exp.amount_estimated or 0.0
        self.amount_preventiva_unit = exp.amount_estimated_unit or 0.0

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
                    "amount_estimated_line": line.amount_estimated_line or 0.0,
                    "amount_final_line": line.amount_final_line or 0.0,
                }
            )
        self.line_ids = [(0, 0, v) for v in lines_vals]
        return True

    def action_generate_initial(self):
        """Alias retrocompatible."""
        return self.action_generate_preventiva()

    def action_generate_final(self):
        """Pasa a definitiva: mismo número, completa importes."""
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "final":
            raise UserError(_("La etapa actual no permite pasar a Solicitud de Gasto definitiva."))
        if not self.number or self.number == "/":
            raise UserError(_("Primero debe existir la Solicitud de Gasto preventiva con número asignado."))
        if not self.line_ids:
            raise UserError(_("La Solicitud de Gasto preventiva no tiene líneas."))

        self.spend_state = "definitiva"
        if not self.date_definitiva:
            self.date_definitiva = fields.Date.context_today(self)

        self.amount_definitiva = exp.amount_estimated_confirmed or 0.0
        self.amount_definitiva_unit = exp.amount_estimated_confirmed_unit or 0.0
        # Refrescar importes definitivos desde las líneas actuales del expediente
        exp_lines = exp.line_ids.sorted(key=lambda l: (l.sequence, l.id))
        snap_lines = self.line_ids.sorted(key=lambda l: (l.sequence, l.id))
        for snap, src in zip(snap_lines, exp_lines):
            if snap.display_type or src.display_type:
                continue
            snap.write(
                {
                    "amount_estimated_line": src.amount_estimated_line or 0.0,
                    "amount_final_line": src.amount_final_line or 0.0,
                }
            )
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
    currency_id = fields.Many2one(related="spend_request_id.currency_id", store=True, readonly=True)
    amount_estimated_line = fields.Monetary(
        string="Importe estimado",
        currency_field="currency_id",
        readonly=True,
    )
    amount_final_line = fields.Monetary(
        string="Importe definitivo",
        currency_field="currency_id",
        readonly=True,
    )

    @api.constrains("product_id", "name", "display_type")
    def _check_name_required(self):
        for line in self:
            if (
                not line.display_type
                and not line.product_id
                and not (line.name and str(line.name).strip())
            ):
                raise ValidationError(_("La descripción es obligatoria cuando no hay producto."))
