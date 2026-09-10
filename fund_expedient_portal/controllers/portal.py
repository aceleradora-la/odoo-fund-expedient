# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)

# Errores de negocio que se muestran al usuario como aviso en la página en
# lugar de romper la petición.
PORTAL_USER_ERRORS = (UserError, ValidationError, AccessError)


class ExpedientCustomerPortal(CustomerPortal):
    _items_per_page = 20

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "expedient_count" in counters:
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
            "page_name": "expedient",
            "expedient_state_label": expedient._portal_state_label(),
            # Solicitudes vigentes primero; las canceladas quedan como historial.
            "expedient_spend_requests": expedient.spend_request_ids.sorted(
                key=lambda s: (s.cancelled, -s.id)
            ),
            "expedient_documents": expedient.document_ids.sorted(
                key=lambda d: (d.stage_id.sequence, d.sequence, d.id)
            ),
            "document_types": request.env["fund.expedient.document.type"].sudo().search([]),
            "is_lease": expedient.contract_kind in ("service_lease", "work_lease"),
        }
        values.update(expedient._portal_stage_nav_values())
        values.update(expedient._portal_action_values())
        values["can_advance_stage"] = (
            values.get("portal_can_previous") or values.get("portal_can_next")
        )
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
        """Expediente (sudo) si el usuario puede verlo; recordset vacío si no.

        Con `access_token` válido alcanza el token (enlaces compartidos). Sin
        token se exige además el criterio del portal; `_document_check_access`
        ya aplicó ACL y reglas de registro del usuario real.
        """
        try:
            expedient_sudo = self._document_check_access(
                "fund.expedient", expedient_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.env["fund.expedient"]
        if access_token:
            return expedient_sudo
        if expedient_sudo and expedient_sudo._portal_user_can_access():
            return expedient_sudo
        return request.env["fund.expedient"]

    def _check_expedient_operator(self, expedient_id):
        """Expediente (sudo) solo si el usuario actual opera su etapa.

        Las acciones de etapa se ejecutan con sudo —un usuario de portal no
        tiene permiso de escritura— así que el permiso funcional se verifica
        acá, con el usuario real, antes de entrar. `can_edit_in_stage` se
        calcula por usuario (`depends_context uid`) y sudo no cambia el uid.
        """
        expedient = self._check_expedient_access(expedient_id)
        if not expedient:
            return expedient
        if expedient.state == "cancel" or not expedient.can_edit_in_stage:
            self._set_portal_flash(
                _("Solo los usuarios asignados a la etapa actual pueden operar este expediente.")
            )
            return request.env["fund.expedient"]
        return expedient

    def _set_portal_flash(self, message, alert_type="danger"):
        request.session["portal_expedient_flash"] = {
            "message": message,
            "type": alert_type,
        }

    def _run_portal_action(self, action, success_message=None):
        """Ejecuta una acción de negocio y traduce el resultado en un aviso.

        Se envuelve en un savepoint: al capturar la excepción para mostrarla,
        la petición termina bien y Odoo confirma la transacción. Sin el
        savepoint quedaban confirmados los cambios hechos antes del error (p.
        ej. una revisión aprobada sin el avance de etapa que la seguía).
        """
        try:
            with request.env.cr.savepoint():
                action()
        except PORTAL_USER_ERRORS as exc:
            self._set_portal_flash(str(exc))
            return False
        if success_message:
            self._set_portal_flash(success_message, "success")
        return True

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
            "holder": {
                "label": _("En mi poder"),
                "domain": [("holder_user_ids", "in", request.env.user.id)],
            },
            "open": {
                "label": _("En curso"),
                "domain": [("state", "not in", ("cancel", "approved", "no_award"))],
            },
        }

        if not sortby or sortby not in searchbar_sortings:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]
        if not filterby or filterby not in searchbar_filters:
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
        # La búsqueda aplica ACL y reglas del usuario real; el resultado se
        # muestra con sudo para leer nombres de catálogos relacionados
        # (solicitante, tipo, etapa) sin abrirle esos modelos al portal.
        expedients = Expedient.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager["offset"],
        ).sudo()
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
        expedient = self._check_expedient_operator(expedient_id)
        if not expedient:
            return request.redirect(f"/my/expedients/{expedient_id}")
        self._run_portal_action(expedient.action_next_stage)
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
        expedient = self._check_expedient_operator(expedient_id)
        if not expedient:
            return request.redirect(f"/my/expedients/{expedient_id}")
        self._run_portal_action(expedient.action_previous_stage)
        return request.redirect(expedient.get_portal_url())

    @http.route(
        ["/my/expedients/<int:expedient_id>/spend_request/<string:phase>"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_expedient_create_spend_request(self, expedient_id, phase, **post):
        """Genera la Solicitud (preventiva o definitiva) desde el portal.

        Sin esto un usuario de portal quedaba trabado en toda etapa que exige
        Solicitud: el requisito se mostraba pero no había forma de cumplirlo.
        """
        expedient = self._check_expedient_operator(expedient_id)
        if not expedient:
            return request.redirect(f"/my/expedients/{expedient_id}")
        actions = {
            "preventiva": expedient.action_create_spend_request_initial,
            "definitiva": expedient.action_create_spend_request_final,
        }
        if phase not in actions:
            return request.not_found()
        label = expedient._spend_request_doc_label()
        self._run_portal_action(
            actions[phase],
            _("%(doc)s %(phase)s generada.", doc=label, phase=phase),
        )
        return request.redirect(expedient.get_portal_url(anchor="spend_requests"))

    @http.route(
        ["/my/expedients/<int:expedient_id>/documents/upload"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def portal_expedient_upload_document(self, expedient_id, **post):
        """Sube un documento a la etapa actual del expediente.

        `fund.expedient.document.create` ya valida —con el usuario real,
        porque sudo no cambia el uid— que quien sube opera la etapa y que el
        documento entra en la etapa actual; también numera y autovincula la
        Disposición o Resolución de la etapa si hay una sola.
        """
        expedient = self._check_expedient_operator(expedient_id)
        if not expedient:
            return request.redirect(f"/my/expedients/{expedient_id}")
        upload = post.get("file")
        if upload is None or not getattr(upload, "filename", ""):
            self._set_portal_flash(_("Seleccione un archivo para subir."))
            return request.redirect(expedient.get_portal_url(anchor="documents"))
        document_type_id = post.get("document_type_id")
        vals = {
            "expedient_id": expedient.id,
            "stage_id": expedient.stage_id.id,
            "name": (post.get("name") or "").strip() or upload.filename,
            "file_name": upload.filename,
            "file_data": base64.b64encode(upload.read()),
            "document_type_id": int(document_type_id) if document_type_id else False,
        }

        def create_document():
            request.env["fund.expedient.document"].sudo().create(vals)

        self._run_portal_action(create_document, _("Documento subido."))
        return request.redirect(expedient.get_portal_url(anchor="documents"))
