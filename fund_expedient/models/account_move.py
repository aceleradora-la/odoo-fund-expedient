# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    expedient_ids = fields.Many2many(
        "fund.expedient",
        "fund_expedient_account_move_rel",
        "move_id",
        "expedient_id",
        string="Expedientes",
        copy=False,
        help="Expedientes a los que se imputa esta factura. Se puede cargar una factura "
        "directa (sin orden de compra) y asociarla acá. Solo se ofrecen los expedientes "
        "del proveedor de la factura: debe figurar como proveedor recomendado del "
        "expediente o tener una orden de compra suya.",
    )
    allowed_expedient_ids = fields.Many2many(
        "fund.expedient",
        compute="_compute_allowed_expedient_ids",
        string="Expedientes disponibles",
        help="Campo técnico: alimenta el domain del selector de expedientes según el "
        "proveedor/cliente de la factura.",
    )

    @api.depends("partner_id", "move_type", "company_id")
    def _compute_allowed_expedient_ids(self):
        """Expedientes seleccionables según el partner y el tipo de factura.

        - Factura/nota de proveedor: expedientes de gasto donde el proveedor figura
          como recomendado (cabecera o líneas) o es proveedor de una OC vinculada.
        - Factura/nota de cliente: expedientes de ingreso (el expediente no tiene un
          campo de cliente, así que ahí el filtro es solo por tipo de operación).
        """
        Expedient = self.env["fund.expedient"]
        for move in self:
            if move.move_type not in (
                "in_invoice",
                "in_refund",
                "out_invoice",
                "out_refund",
            ):
                move.allowed_expedient_ids = Expedient
                continue

            company_domain = [("company_id", "in", [False, move.company_id.id])]
            if move.move_type in ("out_invoice", "out_refund"):
                move.allowed_expedient_ids = Expedient.search(
                    company_domain + [("operation_type", "=", "income")]
                )
                continue

            partner = move.partner_id
            if not partner:
                move.allowed_expedient_ids = Expedient
                continue
            # Aceptar tanto el contacto de la factura como su empresa: los
            # proveedores recomendados se cargan a nivel compañía.
            partner_ids = list({partner.id, partner.commercial_partner_id.id})
            by_recommended = Expedient.search(
                company_domain
                + [
                    ("operation_type", "=", "expense"),
                    "|",
                    ("recommended_supplier_ids", "in", partner_ids),
                    ("line_ids.recommended_supplier_ids", "in", partner_ids),
                ]
            )
            # `purchase_order_ids` está restringido al grupo de Compras: se lee con
            # sudo para que el filtro funcione también para usuarios de Contabilidad.
            by_order = Expedient.sudo().search(
                company_domain
                + [
                    ("operation_type", "=", "expense"),
                    ("purchase_order_ids.partner_id", "in", partner_ids),
                ]
            )
            move.allowed_expedient_ids = by_recommended | Expedient.browse(by_order.ids)
    payment_date = fields.Date(
        string="Fecha de pago",
        compute="_compute_payment_delay",
        store=True,
        help="Fecha en que la factura de proveedor quedó totalmente pagada "
        "(fecha del último asiento conciliado contra la línea a pagar).",
    )
    payment_delay_days = fields.Float(
        string="Días hasta el pago",
        compute="_compute_payment_delay",
        store=True,
        aggregator="avg",
        help="Días entre la fecha de la factura y la fecha en que quedó pagada. "
        "Solo se calcula para facturas de proveedor pagadas; el resto queda en 0. "
        "Medida para promediar tiempos de pago en pivote/gráficos "
        "(filtrar payment_state in ('paid','in_payment') para evitar sesgo por los ceros).",
    )

    @api.depends(
        "move_type",
        "invoice_date",
        "payment_state",
        "line_ids.matched_debit_ids.max_date",
        "line_ids.matched_credit_ids.max_date",
    )
    def _compute_payment_delay(self):
        for move in self:
            pay_date = False
            if (
                move.move_type == "in_invoice"
                and move.invoice_date
                and move.payment_state in ("paid", "in_payment")
            ):
                payable_lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type
                    in ("liability_payable", "asset_receivable")
                )
                partials = payable_lines.matched_debit_ids | payable_lines.matched_credit_ids
                dates = [d for d in partials.mapped("max_date") if d]
                if dates:
                    pay_date = max(dates)
            move.payment_date = pay_date
            move.payment_delay_days = (
                (pay_date - move.invoice_date).days
                if pay_date and move.invoice_date
                else 0.0
            )

    @api.onchange("expedient_ids")
    def _onchange_expedient_ids_analytic(self):
        """Si todos los expedientes apuntan a la misma cuenta analítica,
        se sugiere para las líneas de factura sin distribución cargada."""
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            analytics = move.expedient_ids.mapped("analytic_account_id").filtered(lambda a: a)
            if len(analytics) == 1:
                analytic = analytics[0]
                for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                    if not line.analytic_distribution:
                        line.analytic_distribution = {str(analytic.id): 100.0}

    def _apply_expedient_analytic_distribution(self):
        """Propaga la cuenta analítica del expediente a las líneas sin distribución."""
        for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
            if not move.expedient_ids:
                continue
            analytics = move.expedient_ids.mapped("analytic_account_id").filtered(lambda a: a)
            if len(analytics) != 1:
                continue
            analytic = analytics[0]
            lines_to_update = move.invoice_line_ids.filtered(
                lambda l: not l.display_type and not l.analytic_distribution
            )
            if lines_to_update:
                lines_to_update.write({"analytic_distribution": {str(analytic.id): 100.0}})

    def _linked_expedients_for_recompute(self):
        """Expedientes cuyos totales dependen de estas facturas.

        Incluye los vinculados directamente y los que llegan por la orden de compra
        de las líneas (una factura de OC impacta el expediente de esa orden).
        """
        expedients = self.mapped("expedient_ids")
        for move in self:
            if move.move_type in ("in_invoice", "in_refund"):
                for po in move.invoice_line_ids.purchase_line_id.order_id:
                    if po.expedient_ids:
                        expedients |= po.expedient_ids
        return expedients

    @api.model_create_multi
    def create(self, vals_list):
        """Igual que `write`: propagar analítica y refrescar totales del expediente.

        `amount_committed` / `amount_real` del expediente son campos almacenados sin
        dependencias sobre facturas (se invalidan a mano), así que una factura creada
        ya vinculada —o creada desde una OC— dejaba los totales sin actualizar y el
        expediente mostraba «real» en cero.
        """
        moves = super().create(vals_list)
        moves._apply_expedient_analytic_distribution()
        expedients = moves._linked_expedients_for_recompute()
        if expedients:
            expedients._invalidate_commercial_computes()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if "expedient_ids" in vals:
            self._apply_expedient_analytic_distribution()
        if any(
            f in vals
            for f in ("expedient_ids", "state", "amount_total", "currency_id", "invoice_line_ids")
        ):
            # Recompute de importes comprometidos/reales del expediente
            # cuando cambia la factura o su vínculo.
            expedients = self._linked_expedients_for_recompute()
            if expedients:
                expedients._invalidate_commercial_computes()
        return res
