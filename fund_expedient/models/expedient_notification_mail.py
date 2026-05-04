# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FundExpedientNotificationMail(models.Model):
    _name = "fund.expedient.notification.mail"
    _description = "Registro de notificación por correo (expediente)"
    _order = "create_date desc, id desc"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
        index=True,
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        required=True,
        ondelete="restrict",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Oferente",
        required=True,
        ondelete="restrict",
        index=True,
    )
    mail_mail_id = fields.Many2one(
        "mail.mail",
        string="Correo",
        ondelete="set null",
    )
    mail_server_id = fields.Many2one(
        "ir.mail_server",
        string="Servidor saliente",
        ondelete="set null",
    )
    template_id = fields.Many2one(
        "mail.template",
        string="Plantilla",
        ondelete="set null",
    )
    subject = fields.Char(string="Asunto")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "fund_expedient_notification_mail_attachment_rel",
        "notification_mail_id",
        "attachment_id",
        string="Adjuntos enviados",
    )
    # Misma selección que mail.mail.state (no duplicar selection en related: Odoo 18 lo ignora y avisa).
    state = fields.Selection(
        related="mail_mail_id.state",
        string="Estado correo",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="expedient_id.company_id",
        store=True,
    )
