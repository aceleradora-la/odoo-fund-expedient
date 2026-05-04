# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FundExpedientNotificationSendWizard(models.TransientModel):
    _name = "fund.expedient.notification.send.wizard"
    _description = "Enviar notificación a oferentes (expediente)"

    expedient_id = fields.Many2one(
        "fund.expedient",
        string="Expediente",
        required=True,
        ondelete="cascade",
    )
    stage_id = fields.Many2one(
        "fund.expedient.stage",
        string="Etapa",
        required=True,
        readonly=True,
    )
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Plantilla",
        domain="[('model_id.model', '=', 'fund.expedient')]",
        required=True,
    )
    mail_server_id = fields.Many2one(
        "ir.mail_server",
        string="Servidor saliente",
    )
    document_ids = fields.Many2many(
        "fund.expedient.document",
        string="Documentos a adjuntar",
        domain="[('expedient_id', '=', expedient_id)]",
        help="Archivos cargados en el expediente que se adjuntarán al correo.",
    )
    pending_summary = fields.Text(
        string="Destinatarios pendientes",
        compute="_compute_pending_partners",
        store=False,
        readonly=True,
    )
    info_message = fields.Char(
        string="Estado",
        compute="_compute_pending_partners",
        store=False,
    )

    @api.depends("expedient_id", "stage_id")
    def _compute_pending_partners(self):
        for wiz in self:
            if not wiz.expedient_id or not wiz.stage_id:
                wiz.pending_summary = ""
                wiz.info_message = ""
                continue
            exp = wiz.expedient_id
            partners = exp._get_responded_rfq_partners()
            if not partners:
                wiz.pending_summary = ""
                wiz.info_message = _(
                    "No hay oferentes con cotización respondida vinculada a este expediente."
                )
                continue
            done = self.env["fund.expedient.notification.mail"].search(
                [
                    ("expedient_id", "=", exp.id),
                    ("stage_id", "=", wiz.stage_id.id),
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sent"),
                ]
            ).mapped("partner_id")
            pending = partners - done
            wiz.pending_summary = "\n".join(pending.mapped("name")) if pending else ""
            if not pending:
                wiz.info_message = _("Todos los oferentes requeridos ya fueron notificados en esta etapa.")
            else:
                wiz.info_message = _(
                    "Faltan notificar a: %s"
                    % ", ".join(pending.mapped("name")[:20])
                )

    def action_send(self):
        self.ensure_one()
        exp = self.expedient_id
        if not exp or not self.stage_id:
            raise UserError(_("Datos incompletos."))
        assign = self.env["fund.expedient.type.stage.assign"].search(
            [
                ("type_id", "=", exp.type_id.id),
                ("stage_id", "=", self.stage_id.id),
            ],
            limit=1,
        )
        if not self.mail_template_id:
            raise UserError(_("Debe indicar una plantilla de correo."))
        partners = exp._get_responded_rfq_partners()
        if not partners:
            raise UserError(
                _(
                    "No hay oferentes con cotización respondida. No se puede enviar la notificación."
                )
            )
        done = self.env["fund.expedient.notification.mail"].search(
            [
                ("expedient_id", "=", exp.id),
                ("stage_id", "=", self.stage_id.id),
                ("partner_id", "in", partners.ids),
                ("state", "=", "sent"),
            ]
        ).mapped("partner_id")
        to_send = partners - done
        if not to_send:
            return {"type": "ir.actions.act_window_close"}
        server = self.mail_server_id or (assign.notification_mail_server_id if assign else False)
        Log = self.env["fund.expedient.notification.mail"]
        template = self.mail_template_id
        Attachment = self.env["ir.attachment"]
        for partner in to_send:
            if not partner.email:
                raise UserError(
                    _("El contacto %s no tiene email configurado.") % partner.display_name
                )
            mail_server_id = server.id if server else False
            mail_id = template.send_mail(
                exp.id,
                force_send=False,
                email_values={
                    "email_to": partner.email,
                    "mail_server_id": mail_server_id,
                },
            )
            mail = self.env["mail.mail"].browse(mail_id).exists()
            if not mail:
                raise UserError(_("No se pudo crear el correo saliente."))
            att_ids = []
            for doc in self.document_ids:
                atts = Attachment.search(
                    [
                        ("res_model", "=", "fund.expedient.document"),
                        ("res_id", "=", doc.id),
                        ("res_field", "=", "file_data"),
                    ],
                    limit=1,
                )
                if atts:
                    new_att = atts[0].copy(
                        {
                            "res_model": "mail.mail",
                            "res_id": mail.id,
                            "res_field": False,
                        }
                    )
                    att_ids.append(new_att.id)
                elif doc.file_data:
                    name = doc.file_name or doc.name or "adjunto"
                    new_att = Attachment.create(
                        {
                            "name": name,
                            "type": "binary",
                            "datas": doc.file_data,
                            "res_model": "mail.mail",
                            "res_id": mail.id,
                            "mimetype": "application/octet-stream",
                        }
                    )
                    att_ids.append(new_att.id)
            if att_ids:
                mail.write({"attachment_ids": [(6, 0, att_ids)]})
            mail.send()
            Log.create(
                {
                    "expedient_id": exp.id,
                    "stage_id": self.stage_id.id,
                    "partner_id": partner.id,
                    "mail_mail_id": mail.id,
                    "mail_server_id": mail_server_id or False,
                    "template_id": template.id,
                    "subject": mail.subject,
                    "attachment_ids": [(6, 0, att_ids)],
                }
            )
        return {"type": "ir.actions.act_window_close"}
