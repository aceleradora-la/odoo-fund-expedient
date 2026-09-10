# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.fund_expedient_portal.controllers.portal import (
    ExpedientCustomerPortal as ExpedientCustomerPortalBase,
)

TIER_PORTAL_MODELS = {
    "fund.expedient",
    "fund.expedient.spend.request",
    "fund.expedient.disposition",
    "fund.expedient.resolution",
}

PORTAL_USER_ERRORS = (UserError, ValidationError, AccessError, MissingError)


class ExpedientTierPortalMixin:
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "pending_tier_count" in counters:
            values["pending_tier_count"] = len(self._portal_pending_tier_records())
        return values

    def _portal_pending_tier_records(self):
        """Registros (de varios modelos) que esperan la aprobación del usuario ahora.

        Se busca con el usuario real —ACL y reglas de registro del portal— y se
        filtra por `can_review`, que se calcula por usuario: «es mi turno».
        """
        Expedient = request.env["fund.expedient"]
        expedient_ids = Expedient.search(Expedient._portal_expedient_base_domain()).ids
        pending = []
        for model_name in sorted(TIER_PORTAL_MODELS):
            Model = request.env[model_name]
            if not Model.has_access("read"):
                continue
            if model_name == "fund.expedient":
                domain = [("id", "in", expedient_ids)]
            else:
                domain = [("expedient_id", "in", expedient_ids), ("cancelled", "=", False)]
            records = Model.search(domain).filtered(lambda r: r.can_review)
            pending.extend(records)
        return pending

    def _tier_review_status_labels(self):
        selection = request.env["tier.review"].fields_get(["status"])["status"]["selection"]
        return dict(selection)

    def _prepare_tier_portal_values(self, record):
        """Valores QWeb para el panel de validación de un registro."""
        reviews = record._portal_tier_current_reviews()
        status = getattr(record, "stage_validation_status", None) or getattr(
            record, "validation_status", "no"
        )
        status_labels = {
            "no": _("Sin validación"),
            "waiting": _("En espera"),
            "pending": _("Pendiente"),
            "rejected": _("Rechazada"),
            "validated": _("Aprobada"),
        }
        review_labels = self._tier_review_status_labels()
        user = request.env.user
        my_pending_reviews = reviews.filtered(
            lambda r: user in r.reviewer_ids and r.status == "pending"
        )
        # Un visitante con enlace compartido no opera nada: sin esto, una etapa
        # sin asignación configurada (donde `can_edit_in_stage` es True para
        # cualquiera) le mostraba botones que después exigen iniciar sesión.
        can_review = not user._is_public() and bool(getattr(record, "can_review", False))
        can_drive = not user._is_public() and record._portal_tier_can_drive_flow()
        return {
            "record": record,
            "tier_reviews": reviews.sorted("sequence"),
            "tier_my_pending_reviews": my_pending_reviews,
            "tier_status": status,
            "tier_status_label": status_labels.get(status, status),
            "tier_review_labels": review_labels,
            "tier_can_review": can_review,
            # Solicitar y reiniciar solo para quien opera la etapa: es lo que
            # exige el servidor, así el botón no promete lo que después falla.
            "tier_need_validation": bool(
                can_drive and getattr(record, "need_validation", False)
            ),
            "tier_can_restart": bool(
                can_drive and getattr(record, "can_restart_validation_stage", False)
            ),
            "tier_has_comment": bool(getattr(record, "has_comment", False)),
            "tier_model": record._name,
            "tier_res_id": record.id,
        }

    def _expedient_get_page_view_values(self, expedient, access_token, **kwargs):
        values = super()._expedient_get_page_view_values(
            expedient, access_token, **kwargs
        )
        values["expedient_tier"] = self._prepare_tier_portal_values(expedient)
        values["sg_tier_map"] = {
            sg.id: self._prepare_tier_portal_values(sg)
            for sg in expedient.spend_request_ids.filtered(lambda s: not s.cancelled)
        }
        values["disp_tier_map"] = {
            disp.id: self._prepare_tier_portal_values(disp)
            for disp in expedient.disposition_ids.filtered(lambda d: not d.cancelled)
        }
        values["resol_tier_map"] = {
            resol.id: self._prepare_tier_portal_values(resol)
            for resol in expedient.resolution_ids.filtered(lambda r: not r.cancelled)
        }
        return values

    def _get_tier_record(self, model, res_id):
        """Registro sobre el que actuar, verificado con el usuario real."""
        if model not in TIER_PORTAL_MODELS:
            raise AccessError(_("Modelo no permitido."))
        try:
            record = request.env[model].browse(int(res_id or 0))
        except ValueError:
            raise AccessError(_("Registro no válido."))
        if not record.exists():
            raise MissingError(_("Registro no encontrado."))
        record.check_access("read")
        record._portal_tier_check_access()
        return record

    def _tier_redirect_url(self, record):
        if record._name == "fund.expedient":
            return record.get_portal_url()
        expedient = record.expedient_id
        anchor = ""
        if record._name == "fund.expedient.spend.request":
            anchor = f"#sg_{record.id}"
        elif record._name == "fund.expedient.disposition":
            anchor = f"#disp_{record.id}"
        elif record._name == "fund.expedient.resolution":
            anchor = f"#resol_{record.id}"
        return f"{expedient.get_portal_url()}{anchor}"

    @http.route(
        [
            "/my/expedients/pending_reviews",
            "/my/expedients/pending_reviews/page/<int:page>",
        ],
        type="http",
        auth="user",
        website=True,
    )
    def portal_pending_tier_reviews(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        pending = self._portal_pending_tier_records()
        pending_items = []
        for rec in pending:
            expedient = rec if rec._name == "fund.expedient" else rec.expedient_id
            pending_items.append(
                {
                    "record": rec,
                    "url": self._tier_redirect_url(rec),
                    "tier_data": self._prepare_tier_portal_values(rec),
                    "expedient": expedient.sudo(),
                }
            )
        flash = request.session.pop("portal_expedient_flash", None)
        values.update(
            {
                "page_name": "pending_tier",
                "pending_records": pending,
                "pending_items": pending_items,
                "title": _("Aprobaciones pendientes"),
                "portal_flash": flash,
            }
        )
        return request.render(
            "fund_expedient_tier_validation_portal.portal_pending_tier_reviews",
            values,
        )

    @http.route(
        ["/my/tier/action"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_tier_action(self, **post):
        model = post.get("model")
        res_id = post.get("res_id")
        action = post.get("action")
        comment = post.get("comment", "")
        redirect_url = "/my/expedients/pending_reviews"
        messages = {
            "validate": _("Aprobación registrada correctamente."),
            "reject": _("Rechazo registrado correctamente."),
            "request": _(
                "Validación solicitada. Los aprobadores podrán aprobar desde este "
                "expediente o desde Aprobaciones pendientes."
            ),
            "restart": _("Validación reiniciada."),
        }
        try:
            # Savepoint: al capturar el error para mostrarlo, la petición
            # termina bien y Odoo confirma; sin esto quedaban confirmados los
            # cambios previos al error (p. ej. la revisión aprobada sin el
            # avance de etapa que la seguía).
            with request.env.cr.savepoint():
                record = self._get_tier_record(model, res_id)
                referrer = request.httprequest.referrer or ""
                if "/my/expedients/pending_reviews" not in referrer:
                    redirect_url = self._tier_redirect_url(record)
                if action == "validate":
                    record.portal_action_validate_tier(comment)
                elif action == "reject":
                    record.portal_action_reject_tier(comment)
                elif action == "request":
                    record.portal_action_request_validation()
                elif action == "restart":
                    record.portal_action_restart_validation()
                else:
                    raise UserError(_("Acción no válida."))
            self._set_portal_flash(messages[action], "success")
        except PORTAL_USER_ERRORS as exc:
            self._set_portal_flash(str(exc))
        return request.redirect(redirect_url)


class ExpedientCustomerPortal(ExpedientTierPortalMixin, ExpedientCustomerPortalBase):
    pass
