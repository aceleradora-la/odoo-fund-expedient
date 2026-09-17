# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

# Método de la localización de ADHOC (`l10n_ar_edi_ux`) que completa el
# contacto desde el padrón de ARCA. Es el mismo que llama el botón «Update
# From AFIP» de la ficha del contacto.
PADRON_METHOD = "button_update_partner_data_from_afip"


class ExpedientSupplierCuit(models.AbstractModel):
    """Servicio detrás del widget «Proveedores recomendados por CUIT».

    El widget busca el contacto por CUIT y lo agrega a los proveedores del
    expediente o de la línea; si no existe, lo crea con los datos del padrón
    de ARCA. Es el único camino por el que un usuario de Expedientes crea un
    contacto: el permiso sobre Contactos no se toca, la creación corre con
    `sudo` y solo prospera si el padrón devolvió datos —nunca se crea un
    contacto con el CUIT como único dato—.
    """

    _name = "fund.expedient.supplier.cuit"
    _description = "Proveedores recomendados por CUIT"

    # ------------------------------------------------------------------
    # CUIT
    # ------------------------------------------------------------------

    @api.model
    def _cuit_digits(self, value):
        return re.sub(r"\D", "", value or "")

    @api.model
    def _cuit_format(self, digits):
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"

    @api.model
    def _cuit_is_valid(self, digits):
        """Dígito verificador del CUIT (módulo 11)."""
        if len(digits) != 11 or not digits.isdigit():
            return False
        weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
        total = sum(int(d) * w for d, w in zip(digits[:10], weights))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        elif check == 10:
            check = 9
        return check == int(digits[10])

    @api.model
    def _find_partner(self, digits):
        """Contacto cuyo CUIT es exactamente ese.

        El CUIT puede estar guardado con o sin guiones; la localización además
        expone `l10n_ar_vat` ya normalizado cuando está instalada. Se devuelve
        el contacto que coincide, no su empresa: un monotributista con CUIT
        propio que figura como contacto de una empresa es un proveedor en sí
        mismo. Entre varios con el mismo CUIT gana la empresa y el activo.
        """
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        # El número de identificación se guarda en `vat` (la localización lo
        # normaliza a dígitos, pero puede haber cargas con guiones).
        domain = ["|", ("vat", "=", digits), ("vat", "=", self._cuit_format(digits))]
        # `l10n_ar_vat` es calculado y NO buscable: si se lo pone en un dominio,
        # el ORM descarta la condición con un error en el log y la reemplaza
        # por «verdadero», con lo que la búsqueda devolvía todos los contactos
        # y se quedaba con el primero (la propia compañía). Solo se usa si la
        # versión instalada lo hizo buscable.
        field = Partner._fields.get("l10n_ar_vat")
        if field and (field.store or field.search):
            domain = ["|", ("l10n_ar_vat", "=", digits)] + domain
        partners = Partner.search(domain)
        return partners.sorted(key=lambda p: (not p.is_company, not p.active, p.id))[:1]

    @api.model
    def _partner_payload(self, partner):
        return {
            "id": partner.id,
            "display_name": partner.sudo().display_name,
            "vat": partner.sudo().vat or "",
        }

    @api.model
    def _padron_available(self):
        return hasattr(self.env["res.partner"], PADRON_METHOD)

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------

    @api.model
    def _check_user(self, expedient_id=False):
        """Quien agrega tiene que ser usuario de Expedientes y operar la etapa.

        Se verifica con el usuario real antes de cualquier `sudo`. La relación
        en sí la escribe el formulario al guardar, con los candados de etapa y
        de validación del expediente; acá se protege la creación del contacto.
        """
        if not self.env.user.has_group("fund_expedient.group_fund_expedient_user"):
            raise AccessError(_("Solo los usuarios de Expedientes pueden agregar proveedores."))
        expedient = self.env["fund.expedient"]
        if expedient_id:
            expedient = expedient.browse(int(expedient_id)).exists()
        if expedient and not expedient.can_edit_in_stage:
            raise AccessError(
                _(
                    "Solo los usuarios asignados a la etapa «%s» pueden modificar los "
                    "proveedores de este expediente."
                )
                % (expedient.stage_id.name or "")
            )
        return expedient

    # ------------------------------------------------------------------
    # API del widget
    # ------------------------------------------------------------------

    @api.model
    def find_partner_by_cuit(self, cuit):
        """Resultado de la búsqueda, listo para que el widget lo muestre."""
        self._check_user()
        digits = self._cuit_digits(cuit)
        if not self._cuit_is_valid(digits):
            return {
                "valid": False,
                "message": _("El CUIT %s no es válido: revise los dígitos.") % (cuit or ""),
            }
        partner = self._find_partner(digits)
        if partner:
            message = ""
            if not partner.active:
                message = _("El contacto está archivado; se agrega igual.")
            return {
                "valid": True,
                "found": True,
                "partner": self._partner_payload(partner),
                "message": message,
            }
        available = self._padron_available()
        return {
            "valid": True,
            "found": False,
            "padron_available": available,
            "message": (
                _("No hay un contacto con el CUIT %s.") % self._cuit_format(digits)
                if available
                else _(
                    "No hay un contacto con el CUIT %s. La localización de ARCA "
                    "(l10n_ar_edi_ux) no está instalada: debe crearse desde Contactos."
                )
                % self._cuit_format(digits)
            ),
        }

    @api.model
    def create_partner_from_cuit(self, cuit, expedient_id=False):
        """Crea el contacto desde el padrón de ARCA y lo devuelve al widget."""
        expedient = self._check_user(expedient_id)
        digits = self._cuit_digits(cuit)
        if not self._cuit_is_valid(digits):
            raise UserError(_("El CUIT %s no es válido: revise los dígitos.") % (cuit or ""))
        partner = self._find_partner(digits)
        if not partner:
            partner = self._create_partner_from_padron(digits, expedient)
        return self._partner_payload(partner)

    @api.model
    def _create_partner_from_padron(self, digits, expedient):
        """Contacto nuevo con los datos del padrón; sin datos, no se crea.

        Se crea un contacto mínimo (CUIT, tipo de identificación, país) y se
        lo completa con el método de la localización. Todo dentro de un
        savepoint: si el padrón falla o no devuelve nada, no queda ningún
        contacto a medio cargar.
        """
        Partner = self.env["res.partner"].sudo()
        if not self._padron_available():
            raise UserError(
                _(
                    "La localización de ARCA (l10n_ar_edi_ux) no está instalada: "
                    "el contacto debe crearse desde Contactos."
                )
            )
        formatted = self._cuit_format(digits)
        placeholder = _("CUIT %s") % formatted
        vals = {
            "name": placeholder,
            "vat": digits,
            "is_company": True,
            "supplier_rank": 1,
            "company_id": False,
        }
        cuit_type = self.env.ref("l10n_ar.it_cuit", raise_if_not_found=False)
        if cuit_type:
            vals["l10n_latam_identification_type_id"] = cuit_type.id
        argentina = self.env.ref("base.ar", raise_if_not_found=False)
        if argentina:
            vals["country_id"] = argentina.id
        try:
            with self.env.cr.savepoint():
                partner = Partner.create(vals)
                getattr(partner, PADRON_METHOD)()
                if not partner.name or partner.name == placeholder:
                    raise UserError(_("El padrón no devolvió datos."))
        except UserError as exc:
            raise UserError(
                _(
                    "No se pudo crear el proveedor con CUIT %(cuit)s desde ARCA: %(error)s "
                    "No se creó ningún contacto.",
                    cuit=formatted,
                    error=str(exc).strip(),
                )
            ) from exc
        partner.message_post(
            body=_(
                "Contacto creado desde el padrón de ARCA por %(user)s al cargarlo como "
                "proveedor recomendado del expediente %(expedient)s.",
                user=self.env.user.name,
                expedient=(expedient and expedient.number) or "",
            ),
            subtype_xmlid="mail.mt_note",
        )
        return partner
