# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
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


class ExpedientTierPortalMixin:
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "pending_tier_count" in counters:
            values["pending_tier_count"] = len(self._portal_pending_tier_records())
        return values

    def _portal_pending_tier_records(self):
        """Lista de registros (modelos distintos) con can_review=True."""
        Expedient = request.env["fund.expedient"]
        expedient_ids = Expedient.search(Expedient._portal_expedient_base_domain()).ids
        pending = []
        for model_name in TIER_PORTAL_MODELS:
            Model = request.env[model_name]
            if not Model.has_access("read"):
                continue
            if model_name == "fund.expedient":
                domain = [("id", "in", expedient_ids)]
            else:
                domain = [("expedient_id", "in", expedient_ids)]
            records = Model.search(domain).filtered(lambda r: r.can_review)
            pending.extend(records)
        return pending

    def _prepare_tier_portal_values(self, record):
        """Valores QWeb para panel tier de un registro."""
        if hasattr(record, "_current_context_reviews"):
            reviews = record._current_context_reviews()
        elif hasattr(record, "_current_stage_reviews"):
            reviews = record._current_stage_reviews()
        else:
            reviews = record.review_ids

        status = getattr(record, "stage_validation_status", None) or getattr(
            record, "validation_status", "no"
        )
        user = request.env.user
        my_pending_reviews = reviews.filtered(
            lambda r: user in r.reviewer_ids and r.status == "pending"
        )
        return {
            "record": record,
            "tier_reviews": reviews,
            "tier_my_pending_reviews": my_pending_reviews,
            "tier_status": status,
            "tier_need_validation": bool(getattr(record, "need_validation", False)),
            "tier_can_review": bool(getattr(record, "can_review", False)),
            "tier_can_restart": bool(
                getattr(record, "can_restart_validation_stage", False)
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
            for sg in expedient.spend_request_ids
        }
        values["disp_tier_map"] = {
            disp.id: self._prepare_tier_portal_values(disp)
            for disp in expedient.disposition_ids
        }
        values["resol_tier_map"] = {
            resol.id: self._prepare_tier_portal_values(resol)
            for resol in expedient.resolution_ids
        }
        return values

    def _get_tier_record(self, model, res_id):
        if model not in TIER_PORTAL_MODELS:
            raise AccessError(_("Modelo no permitido."))
        record = request.env[model].browse(int(res_id))
        if not record.exists():
            raise AccessError(_("Registro no encontrado."))
        record.check_access("read")
        if hasattr(record, "_portal_tier_check_access"):
            record._portal_tier_check_access()
        elif model == "fund.expedient":
            if not record._portal_user_can_access():
                raise AccessError(_("Sin acceso."))
        elif not record.expedient_id._portal_user_can_access():
            raise AccessError(_("Sin acceso al expediente."))
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
        url = expedient.get_portal_url()
        return f"{url}{anchor}"

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
            pending_items.append(
                {
                    "record": rec,
                    "url": self._tier_redirect_url(rec),
                    "tier_data": self._prepare_tier_portal_values(rec),
                    "expedient_label": (
                        rec.number or rec.id
                        if rec._name == "fund.expedient"
                        else rec.expedient_id.number or rec.expedient_id.id
                    ),
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
        try:
            record = self._get_tier_record(model, res_id)
            referrer = request.httprequest.referrer or ""
            if "/my/expedients/pending_reviews" in referrer:
                redirect_url = "/my/expedients/pending_reviews"
            else:
                redirect_url = self._tier_redirect_url(record)
            if action == "validate":
                record.portal_action_validate_tier(comment)
                msg = _("Aprobación registrada correctamente.")
            elif action == "reject":
                record.portal_action_reject_tier(comment)
                msg = _("Rechazo registrado correctamente.")
            elif action == "request":
                record.portal_action_request_validation()
                msg = _("Validación solicitada. Los aprobadores asignados podrán aprobar desde este expediente o desde Aprobaciones pendientes.")
            elif action == "restart":
                record.portal_action_restart_validation()
                msg = _("Validación reiniciada.")
            else:
                raise UserError(_("Acción no válida."))
            request.session["portal_expedient_flash"] = {
                "message": msg,
                "type": "success",
            }
        except (UserError, ValidationError, AccessError) as exc:
            request.session["portal_expedient_flash"] = {
                "message": str(exc),
                "type": "danger",
            }
        return request.redirect(redirect_url)


class ExpedientCustomerPortal(ExpedientTierPortalMixin, ExpedientCustomerPortalBase):
    pass
