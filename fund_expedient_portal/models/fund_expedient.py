# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.osv import expression


class FundExpedient(models.Model):
    # Odoo 18: al extender un modelo ya definido con _name en otro módulo
    # (p. ej. expedient_tier_validation), hay que repetir _name aquí para
    # evitar duplicar campos Many2many al mezclar mixins.
    _name = "fund.expedient"
    _inherit = ["fund.expedient", "portal.mixin"]

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/expedients/{rec.id}"

    def _portal_ensure_token(self):
        """Generar el token de acceso sin pasar por el candado de etapa.

        `write()` del expediente exige que quien escribe opere la etapa actual.
        El token es un dato técnico que se escribe cuando el registro lo
        necesita —en la instalación del módulo (con OdooBot) o al compartir el
        enlace— y quien lo dispara no tiene por qué estar asignado a la etapa;
        sin esto la instalación misma fallaba.
        """
        return super(
            FundExpedient, self.with_context(skip_validation_check=True)
        )._portal_ensure_token()

    # ------------------------------------------------------------------
    # Quién ve qué en el portal
    #
    # Un mismo criterio para usuarios internos y de portal: el expediente lo
    # ven quien lo solicitó, quien opera su etapa actual y —solo para usuarios
    # de portal— el partner seguidor o proveedor recomendado. El módulo de
    # validación por niveles suma a los revisores vía `_portal_access_clauses`.
    #
    # La regla de registro (ir.rule) de `security/` repite estas cláusulas: el
    # dominio de acá arma los listados y el chequeo puntual; la regla es lo que
    # el ORM aplica cuando el usuario de portal lee. Tienen que decir lo mismo,
    # si no el listado ofrece expedientes que después no se pueden abrir.
    # ------------------------------------------------------------------

    @api.model
    def _portal_is_portal_user(self, user=None):
        user = user or self.env.user
        return user.has_group("base.group_portal") and not user.has_group("base.group_user")

    @api.model
    def _portal_access_clauses(self, user):
        """Cláusulas (en OR) que dan acceso al expediente en el portal."""
        clauses = [
            ("requestor_id.user_id", "=", user.id),
            ("assignable_user_ids", "in", [user.id]),
        ]
        if self._portal_is_portal_user(user):
            partner = user.partner_id.commercial_partner_id
            clauses += [
                ("message_partner_ids", "child_of", partner.ids),
                ("recommended_supplier_ids", "child_of", partner.ids),
            ]
        return clauses

    @api.model
    def _portal_expedient_base_domain(self):
        """Dominio de visibilidad en portal para el usuario actual."""
        user = self.env.user
        if user._is_public():
            return [("id", "=", False)]
        company_domain = [("company_id", "in", user.company_ids.ids + [False])]
        access_domain = expression.OR([[c] for c in self._portal_access_clauses(user)])
        return expression.AND([company_domain, access_domain])

    def _portal_user_can_access(self):
        """True si el usuario actual puede ver este expediente en el portal.

        Se evalúa el mismo dominio del listado acotado a este registro, con sudo
        —el chequeo es nuestro, no del ORM— y por búsqueda, no en memoria:
        `filtered_domain` no resuelve `child_of`. Así listado y detalle no
        pueden discrepar.
        """
        self.ensure_one()
        user = self.env.user
        if user._is_public():
            return False
        if user.has_group("fund_expedient.group_fund_expedient_manager"):
            return True
        domain = [("id", "=", self.id)] + self._portal_expedient_base_domain()
        return bool(self.sudo().search_count(domain))

    # ------------------------------------------------------------------
    # Botones de etapa en el portal
    #
    # Mismas condiciones que la cabecera del formulario del backend, leídas de
    # los mismos campos (`can_edit_in_stage`, `has_previous_stage`,
    # `has_next_stage`, `stage_requirements_ok`, `holder_reason`). Antes el
    # portal reimplementaba cada requisito por su cuenta y quedaba desfasado en
    # cada cambio del backend; ahora hay una sola fuente de verdad. El módulo
    # de validación por niveles agrega su condición sobre estos valores.
    # ------------------------------------------------------------------

    def _portal_stage_nav_values(self):
        """Valores QWeb para «Etapa anterior» / «Siguiente etapa»."""
        self.ensure_one()
        values = {
            "portal_stage_show_panel": False,
            "portal_can_previous": False,
            "portal_can_next": False,
            "portal_block_previous": "",
            "portal_block_next": "",
        }
        if self.env.user._is_public():
            return values
        # El panel se muestra a quien opera la etapa, sea interno o de portal:
        # el objetivo es que un usuario sin licencia pueda llevar el expediente.
        if not self.can_edit_in_stage:
            return values
        values["portal_stage_show_panel"] = True

        if self.state == "cancel":
            msg = _("El expediente está cancelado.")
            values["portal_block_previous"] = msg
            values["portal_block_next"] = msg
            return values

        awaiting_approval = self.holder_reason in (
            "expedient_approval",
            "spend_request_approval",
        )
        if not self.has_previous_stage:
            values["portal_block_previous"] = _("Ya está en la primera etapa.")
        elif awaiting_approval:
            values["portal_block_previous"] = _(
                "Hay una aprobación en curso; primero hay que reiniciar esa validación."
            )
        else:
            values["portal_can_previous"] = True

        if not self.has_next_stage:
            values["portal_block_next"] = _("Ya está en la última etapa del flujo.")
        elif not self.stage_requirements_ok:
            values["portal_block_next"] = self.stage_requirements_pending
        else:
            values["portal_can_next"] = True
        return values

    def _portal_action_values(self):
        """Acciones de etapa disponibles en el portal además de cambiar de etapa.

        Se ofrecen las que el usuario podría completar desde el portal. Crear
        una Disposición o una Resolución queda fuera: nacen vacías y se
        completan editándolas en el backend, cosa que el portal no permite.
        """
        self.ensure_one()
        can_operate = (
            not self.env.user._is_public()
            and self.state != "cancel"
            and self.can_edit_in_stage
        )
        return {
            "portal_can_operate": can_operate,
            "portal_can_create_sr_preventiva": bool(
                can_operate and self.can_create_spend_request_preventiva
            ),
            "portal_can_create_sr_final": bool(
                can_operate and self.can_create_spend_request_final
            ),
            "portal_spend_request_label": self._spend_request_doc_label(),
            "portal_required_document_types": (
                self._missing_required_document_types() if can_operate else self.env["fund.expedient.document.type"]
            ),
        }

    def _portal_state_label(self):
        self.ensure_one()
        return dict(self._fields["state"]._description_selection(self.env)).get(self.state, "")
