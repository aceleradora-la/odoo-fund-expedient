# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ExpedientConfig(models.Model):
    _name = "fund.expedient.config"
    _description = "Configuración de Expedientes"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    expedient_service_product_id = fields.Many2one(
        "product.product",
        string="Producto servicio para líneas sin producto",
        domain=[
            ("type", "=", "service"),
            ("purchase_ok", "=", True),
        ],
        help="Producto de tipo servicio usado cuando una línea del expediente "
        "solo tiene descripción (sin producto). Se crea una OC con este producto.",
    )
    analytic_plan_id = fields.Many2one(
        "account.analytic.plan",
        string="Plan analítico (Expedientes/Presupuesto)",
        help="Plan analítico estándar de Odoo que se usará para seleccionar cuentas analíticas "
        "en el expediente y para los presupuestos/análisis presupuestario de este módulo.",
    )

    # ------------------------------------------------------------------
    # Avisos por correo
    # ------------------------------------------------------------------
    stage_assigned_template_id = fields.Many2one(
        "mail.template",
        string="Plantilla «Etapa asignada»",
        domain=[("model_id.model", "=", "fund.expedient")],
        default=lambda self: self.env.ref(
            "fund_expedient.mail_template_stage_assigned", raise_if_not_found=False
        ),
        help="Correo que reciben los asignados cuando el expediente entra en una etapa. "
        "El aviso se activa etapa por etapa en el tipo de expediente.",
    )

    # ------------------------------------------------------------------
    # Resumen periódico de pendientes
    # ------------------------------------------------------------------
    digest_active = fields.Boolean(
        string="Enviar resumen de pendientes",
        help="Envía a cada usuario un correo con los expedientes que tiene en su poder "
        "y las aprobaciones que le esperan. Solo se envía a quienes tienen algo pendiente.",
    )
    digest_frequency = fields.Selection(
        selection=[
            ("daily", "Diaria"),
            ("weekly", "Semanal"),
            ("monthly", "Mensual"),
        ],
        string="Frecuencia",
        default="weekly",
    )
    digest_hour = fields.Float(
        string="Hora de envío",
        default=8.0,
        help="Hora del día a partir de la cual se envía, en la zona horaria del "
        "contacto de la compañía.",
    )
    digest_weekday = fields.Selection(
        selection=[
            ("0", "Lunes"),
            ("1", "Martes"),
            ("2", "Miércoles"),
            ("3", "Jueves"),
            ("4", "Viernes"),
            ("5", "Sábado"),
            ("6", "Domingo"),
        ],
        string="Día de la semana",
        default="0",
        help="Solo para frecuencia semanal.",
    )
    digest_monthday = fields.Integer(
        string="Día del mes",
        default=1,
        help="Solo para frecuencia mensual. Se admite del 1 al 28 para que exista en todos los meses.",
    )
    digest_template_id = fields.Many2one(
        "mail.template",
        string="Plantilla del resumen",
        domain=[("model_id.model", "=", "res.users")],
        default=lambda self: self.env.ref(
            "fund_expedient.mail_template_pending_digest", raise_if_not_found=False
        ),
    )
    digest_last_sent = fields.Datetime(
        string="Último envío",
        readonly=True,
        copy=False,
        help="Evita repetir el resumen dentro del mismo período.",
    )

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Solo puede haber una configuración por compañía.",
        )
    ]

    @api.model
    def get_service_product(self, company):
        """Obtener el producto servicio para la compañía."""
        config = self.search([("company_id", "=", company.id)], limit=1)
        return config.expedient_service_product_id

    @api.model
    def get_analytic_plan(self, company):
        """Obtener el plan analítico configurado para la compañía."""
        config = self.search([("company_id", "=", company.id)], limit=1)
        return config.analytic_plan_id

    @api.model
    def get_stage_assigned_template(self, company):
        """Plantilla del aviso de etapa asignada, con la del módulo como respaldo."""
        config = self.search([("company_id", "=", company.id)], limit=1)
        if config.stage_assigned_template_id:
            return config.stage_assigned_template_id
        return self.env.ref(
            "fund_expedient.mail_template_stage_assigned", raise_if_not_found=False
        )

    # ------------------------------------------------------------------
    # Resumen periódico
    # ------------------------------------------------------------------

    def _digest_is_due(self, now):
        """¿Corresponde enviar el resumen en esta corrida?

        El cron corre cada hora; acá se decide según la frecuencia, la hora
        configurada y cuándo se envió por última vez. Comparar contra
        `digest_last_sent` es lo que evita repetir el envío si el cron vuelve a
        correr dentro del mismo período.
        """
        self.ensure_one()
        if not self.digest_active or not self.digest_template_id:
            return False
        if now.hour + now.minute / 60.0 < (self.digest_hour or 0.0):
            return False

        last = self.digest_last_sent
        if self.digest_frequency == "daily":
            return not last or last.date() < now.date()
        if self.digest_frequency == "weekly":
            if str(now.weekday()) != (self.digest_weekday or "0"):
                return False
            return not last or last.date() <= (now.date() - relativedelta(days=6))
        if self.digest_frequency == "monthly":
            if now.day != max(1, min(self.digest_monthday or 1, 28)):
                return False
            return not last or (last.year, last.month) != (now.year, now.month)
        return False

    def _digest_recipient_users(self):
        """Usuarios internos activos de la compañía con algo pendiente."""
        self.ensure_one()
        users = self.env["res.users"].search(
            [
                ("active", "=", True),
                ("share", "=", False),
                ("company_ids", "in", self.company_id.id),
                ("email", "!=", False),
            ]
        )
        return users.filtered(lambda u: u._fund_digest_has_content())

    def _send_digest(self):
        """Enviar el resumen a los usuarios con pendientes de esta compañía."""
        self.ensure_one()
        recipients = self._digest_recipient_users()
        template = self.digest_template_id
        for user in recipients:
            # force_send=False: el despacho queda a cargo del cron de correo.
            template.with_company(self.company_id).send_mail(user.id, force_send=False)
        self.digest_last_sent = fields.Datetime.now()
        return len(recipients)

    def _digest_now(self):
        """Hora local de la compañía.

        El cron corre como OdooBot, que normalmente no tiene zona horaria: sin
        esto la «hora de envío» se interpretaría en UTC y el resumen saldría
        corrido varias horas. Se usa la zona del contacto de la compañía.
        """
        self.ensure_one()
        tz = self.company_id.partner_id.tz or self.env.user.tz or "UTC"
        return fields.Datetime.context_timestamp(
            self.with_context(tz=tz), fields.Datetime.now()
        )

    @api.model
    def _cron_send_pending_digest(self):
        """Punto de entrada del cron horario del resumen de pendientes."""
        for config in self.search([("digest_active", "=", True)]):
            try:
                if not config._digest_is_due(config._digest_now()):
                    continue
                sent = config._send_digest()
                _logger.info(
                    "Resumen de pendientes enviado a %s usuarios (compañía %s).",
                    sent,
                    config.company_id.display_name,
                )
            except Exception as error:
                # Un fallo en una compañía no puede cortar el resto de la corrida.
                _logger.exception(
                    "No se pudo enviar el resumen de pendientes de la compañía %s: %s",
                    config.company_id.display_name,
                    error,
                )
        return True
