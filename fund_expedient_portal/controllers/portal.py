# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class ExpedientCustomerPortal(CustomerPortal):
    _items_per_page = 20

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        Expedient = request.env["fund.expedient"]
        if Expedient.has_access("read"):
            domain = Expedient._portal_expedient_base_domain()
            values["expedient_count"] = Expedient.search_count(domain)
        else:
            values["expedient_count"] = 0
        return values

    def _expedient_get_page_view_values(self, expedient, access_token, **kwargs):
        values = {
            "expedient": expedient,
            "can_advance_stage": expedient._portal_can_advance_stage(),
            "page_name": "expedient",
        }
        history = request.session.get("my_expedients_history", [])
        values.update(
            self._get_page_view_values(
                expedient,
                access_token,
                values,
                "my_expedients_history",
                False,
                **kwargs,
            )
        )
        return values

    def _check_expedient_access(self, expedient_id, access_token=None):
        try:
            expedient_sudo = self._document_check_access(
                "fund.expedient", expedient_id, access_token=access_token
            )
        except AccessError:
            return request.env["fund.expedient"]
        if access_token:
            return expedient_sudo
        if expedient_sudo and expedient_sudo._portal_user_can_access():
            return expedient_sudo
        return request.env["fund.expedient"]

    def _set_portal_flash(self, message, alert_type="danger"):
        request.session["portal_expedient_flash"] = {
            "message": message,
            "type": alert_type,
        }

    @http.route(
        ["/my/expedients", "/my/expedients/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_expedients(self, page=1, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        Expedient = request.env["fund.expedient"]
        domain = Expedient._portal_expedient_base_domain()

        searchbar_sortings = {
            "date": {
                "label": _("Fecha solicitud"),
                "order": "request_date desc, id desc",
            },
            "number": {
                "label": _("Número"),
                "order": "number desc, id desc",
            },
            "stage": {
                "label": _("Etapa"),
                "order": "stage_id, id desc",
            },
        }
        searchbar_filters = {
            "all": {"label": _("Todos"), "domain": []},
            "mine": {
                "label": _("Solicitados por mí"),
                "domain": [("requestor_id.user_id", "=", request.env.user.id)],
            },
            "assigned": {
                "label": _("Asignados a mí"),
                "domain": [("assignable_user_ids", "in", request.env.user.id)],
            },
        }

        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]
        if not filterby:
            filterby = "all"
        domain += searchbar_filters[filterby]["domain"]

        expedient_count = Expedient.search_count(domain)
        pager = portal_pager(
            url="/my/expedients",
            url_args={"sortby": sortby, "filterby": filterby},
            total=expedient_count,
            page=page,
            step=self._items_per_page,
        )
        expedients = Expedient.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session["my_expedients_history"] = expedients.ids[:100]

        values.update(
            {
                "expedients": expedients,
                "page_name": "expedient",
                "pager": pager,
                "default_url": "/my/expedients",
                "searchbar_sortings": searchbar_sortings,
                "searchbar_filters": searchbar_filters,
                "sortby": sortby,
                "filterby": filterby,
            }
        )
        return request.render("fund_expedient_portal.portal_my_expedients", values)

    @http.route(
        ["/my/expedients/<int:expedient_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_expedient_page(self, expedient_id, access_token=None, **kw):
        expedient = self._check_expedient_access(expedient_id, access_token)
        if not expedient:
            return request.redirect("/my")
        values = self._expedient_get_page_view_values(expedient, access_token, **kw)
        flash = request.session.pop("portal_expedient_flash", None)
        if flash:
            values["portal_flash"] = flash
        return request.render("fund_expedient_portal.portal_expedient_page", values)

    @http.route(
        ["/my/expedients/<int:expedient_id>/next_stage"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_expedient_next_stage(self, expedient_id, **post):
        expedient = self._check_expedient_access(expedient_id)
        if not expedient:
            return request.redirect("/my")
        try:
            expedient.action_next_stage()
        except (UserError, ValidationError) as exc:
            self._set_portal_flash(str(exc))
        return request.redirect(expedient.get_portal_url())

    @http.route(
        ["/my/expedients/<int:expedient_id>/previous_stage"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_expedient_previous_stage(self, expedient_id, **post):
        expedient = self._check_expedient_access(expedient_id)
        if not expedient:
            return request.redirect("/my")
        if not hasattr(expedient, "action_previous_stage"):
            self._set_portal_flash(_("No puede volver de etapa en este expediente."))
            return request.redirect(expedient.get_portal_url())
        try:
            expedient.action_previous_stage()
        except (UserError, ValidationError) as exc:
            self._set_portal_flash(str(exc))
        return request.redirect(expedient.get_portal_url())
