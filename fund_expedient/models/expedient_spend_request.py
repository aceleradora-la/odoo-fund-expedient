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
    # Lookup informativo (no se guarda): trae el "Número por tipo" del expediente para
    # identificar visualmente la SG según el tipo. La numeración real vive en el expediente.
    expedient_type_number = fields.Char(
        related="expedient_id.type_number",
        string="Número por tipo (expediente)",
        readonly=True,
        store=False,
        search="_search_expedient_type_number",
    )
    expedient_type_id = fields.Many2one(
        related="expedient_id.type_id",
        string="Tipo de expediente",
        readonly=True,
        store=False,
        search="_search_expedient_type_id",
    )

    # Datos del solicitante y su sector traídos desde el expediente.
    # Se almacenan (store=True) para permitir filtros, agrupaciones y reportes
    # eficientes en la Solicitud de Gasto sin re-leer el expediente.
    requestor_id = fields.Many2one(
        "hr.employee",
        string="Solicitante",
        related="expedient_id.requestor_id",
        store=True,
        readonly=True,
        index=True,
    )
    requestor_department_id = fields.Many2one(
        "hr.department",
        string="Sector requirente",
        related="expedient_id.requestor_department_id",
        store=True,
        readonly=True,
        index=True,
    )
    requestor_department_manager_id = fields.Many2one(
        "hr.employee",
        string="Responsable del sector",
        related="expedient_id.requestor_department_manager_id",
        store=True,
        readonly=True,
        index=True,
    )
    # Datos descriptivos heredados del expediente; almacenados para
    # poder verlos, filtrarlos e imprimirlos en el reporte de SG.
    contract_object = fields.Text(
        string="Objeto de la contratación",
        related="expedient_id.contract_object",
        store=True,
        readonly=True,
    )
    delivery_location = fields.Char(
        string="Lugar de Entrega/Ejecución",
        related="expedient_id.delivery_location",
        store=True,
        readonly=True,
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
        string="Fase SG",
        readonly=True,
        index=True,
    )
    preventiva_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("generated", "Generada"),
            ("approved", "Aprobada"),
        ],
        string="Estado preventiva",
        readonly=True,
        default="draft",
        index=True,
    )
    definitiva_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("generated", "Generada"),
            ("approved", "Aprobada"),
        ],
        string="Estado definitiva",
        readonly=True,
        default="draft",
        index=True,
    )
    date_preventiva = fields.Date(string="Fecha preventiva", readonly=True)
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

    date_definitiva = fields.Date(string="Fecha definitiva", readonly=True)
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
    final_number = fields.Char(
        string="Número definitiva (hist.)",
        readonly=True,
        copy=False,
        default="/",
    )

    # ------------------------------------------------------------------
    # Variación entre preventivo y definitivo
    # ------------------------------------------------------------------
    # Campo calculado y ALMACENADO con la diferencia porcentual entre
    # `amount_definitiva` y `amount_preventiva`. Lo necesitamos almacenado
    # porque base_tier_validation evalúa los dominios de cada tier.definition
    # con `search`, y los dominios sólo pueden referirse a campos guardados.
    #
    # Convención del signo:
    #   - Positivo (+): el definitivo es MAYOR que el preventivo
    #     (sobrecosto / ampliación de la SG).
    #   - Negativo (−): el definitivo es MENOR (ahorro).
    #   - 0.0 cuando no hay preventivo o ambos coinciden.
    amount_diff_pct = fields.Float(
        string="Variación definitivo vs. preventivo (%)",
        compute="_compute_amount_diff_pct",
        store=True,
        readonly=True,
        digits=(16, 2),
        help=(
            "Diferencia porcentual entre el importe definitivo y el preventivo. "
            "Positivo = el definitivo supera al preventivo (sobrecosto). "
            "Negativo = ahorro. 0 si aún no hay preventivo cargado."
        ),
    )

    @api.depends("amount_preventiva", "amount_definitiva")
    def _compute_amount_diff_pct(self):
        """Cálculo de variación % entre definitivo y preventivo.

        Se redondea a 2 decimales en la representación, pero el dato
        almacenado conserva la precisión completa del Float para
        comparaciones en dominios de tier validation sin pérdida.
        """
        for rec in self:
            base = rec.amount_preventiva or 0.0
            final = rec.amount_definitiva or 0.0
            if base:
                rec.amount_diff_pct = (final - base) / base * 100.0
            else:
                rec.amount_diff_pct = 0.0

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

    def _search_expedient_type_number(self, operator, value):
        """Buscar por el número por tipo sin almacenarlo en la SG."""
        return [("expedient_id.type_number", operator, value)]

    def _search_expedient_type_id(self, operator, value):
        """Buscar por tipo de expediente sin duplicar el dato en la SG."""
        return [("expedient_id.type_id", operator, value)]

    _sql_constraints = [
        (
            "expedient_unique",
            "unique(expedient_id)",
            "Ya existe una Solicitud de Gasto para este expediente.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exp_id = vals.get("expedient_id")
            if exp_id and self.search_count([("expedient_id", "=", exp_id)]):
                raise UserError(
                    _("Ya existe una Solicitud de Gasto para este expediente.")
                )
        return super().create(vals_list)

    def _next_number(self, code):
        self.ensure_one()
        seq_env = self.env["ir.sequence"].with_company(self.company_id)
        return seq_env.next_by_code(code) or "/"

    def _line_vals_from_expedient_line(self, line):
        return {
            "sequence": line.sequence,
            "display_type": line.display_type,
            "product_id": line.product_id.id,
            "name": line.name,
            "product_qty": line.product_qty,
            "product_uom_id": line.product_uom_id.id,
            "price_unit_estimated": line.price_unit_estimated or 0.0,
            "amount_estimated_line": line.amount_estimated_line or 0.0,
            "price_unit_final": line.price_unit_final or 0.0,
            "amount_final_line": line.amount_final_line or 0.0,
            "analytic_account_id": line.analytic_account_id.id,
        }

    def _snapshot_lines_from_expedient(self, exp, replace=False):
        """Copia líneas del expediente al snapshot de la SG."""
        self.ensure_one()
        if replace:
            self.line_ids.unlink()
        lines_vals = []
        for line in exp.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            lines_vals.append((0, 0, self._line_vals_from_expedient_line(line)))
        if lines_vals:
            self.write({"line_ids": lines_vals})

    def _sync_lines_from_expedient(self, exp):
        """Actualiza líneas existentes emparejando por sequence e id de origen."""
        self.ensure_one()
        exp_lines = exp.line_ids.sorted(key=lambda l: (l.sequence, l.id))
        snap_lines = self.line_ids.sorted(key=lambda l: (l.sequence, l.id))
        if len(snap_lines) != len(exp_lines):
            self._snapshot_lines_from_expedient(exp, replace=True)
            return
        for snap, src in zip(snap_lines, exp_lines):
            snap.write(self._line_vals_from_expedient_line(src))

    def action_generate_preventiva(self):
        """Genera número único y snapshot preventivo."""
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "preventiva":
            raise UserError(_("La etapa actual no permite crear Solicitud de Gasto preventiva."))
        if not self.number or self.number == "/":
            self.number = self._next_number("fund.expedient.spend.request")
        self.write(
            {
                "spend_state": "preventiva",
                "preventiva_state": "generated",
                "date_preventiva": fields.Date.context_today(self),
                "amount_preventiva": exp.amount_estimated or 0.0,
                "amount_preventiva_unit": exp.amount_estimated_unit or 0.0,
            }
        )
        self._snapshot_lines_from_expedient(exp, replace=True)
        return True

    def action_generate_initial(self):
        return self.action_generate_preventiva()

    def action_generate_final(self):
        """Pasa a definitiva: mismo número, snapshot actualizado desde expediente."""
        self.ensure_one()
        exp = self.expedient_id
        if not exp:
            raise UserError(_("La Solicitud de Gasto debe estar vinculada a un expediente."))
        if exp.stage_id.spend_request_mode != "final":
            raise UserError(_("La etapa actual no permite pasar a Solicitud de Gasto definitiva."))
        if self.preventiva_state != "approved":
            raise UserError(
                _("La Solicitud de Gasto preventiva debe estar aprobada antes de generar la definitiva.")
            )
        if not self.number or self.number == "/":
            raise UserError(_("Primero debe existir la Solicitud de Gasto preventiva con número asignado."))
        if not exp.amount_estimated_confirmed:
            raise UserError(
                _(
                    "Debe cargar un importe definitivo mayor a cero antes de generar "
                    "la Solicitud de Gasto definitiva."
                )
            )

        self.write(
            {
                "spend_state": "definitiva",
                "definitiva_state": "generated",
                "date_definitiva": fields.Date.context_today(self),
                "amount_definitiva": exp.amount_estimated_confirmed or 0.0,
                "amount_definitiva_unit": exp.amount_estimated_confirmed_unit or 0.0,
            }
        )
        self._sync_lines_from_expedient(exp)
        return True

    def _mark_phase_approved(self, phase):
        """Usado por tier validation al completar aprobaciones de una fase."""
        self.ensure_one()
        if phase == "preventiva":
            self.preventiva_state = "approved"
        elif phase == "definitiva":
            self.definitiva_state = "approved"

    def is_phase_approved(self, phase):
        self.ensure_one()
        if phase == "preventiva":
            return self.preventiva_state == "approved"
        if phase == "definitiva":
            return self.definitiva_state == "approved"
        return False

    def is_phase_generated(self, phase):
        self.ensure_one()
        if phase == "preventiva":
            return self.preventiva_state in ("generated", "approved")
        if phase == "definitiva":
            return self.definitiva_state in ("generated", "approved")
        return False

    def action_print_report(self):
        """Imprime el reporte QWeb de la Solicitud de Gasto."""
        self.ensure_one()
        return self.env.ref(
            "fund_expedient.action_report_fund_expedient_spend_request"
        ).report_action(self)


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
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analítica",
        readonly=True,
    )
    price_unit_estimated = fields.Monetary(
        string="Precio unitario estimado",
        currency_field="currency_id",
        readonly=True,
    )
    amount_estimated_line = fields.Monetary(
        string="Importe estimado",
        currency_field="currency_id",
        readonly=True,
    )
    price_unit_final = fields.Monetary(
        string="Precio unitario definitivo",
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
