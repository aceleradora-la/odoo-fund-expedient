# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Modelos que llevan proveedores recomendados. El asistente solo actúa sobre
# estos dos: la lista es cerrada a propósito, porque escribe con `sudo`.
TARGET_MODELS = ("fund.expedient", "fund.expedient.line")

# Método de la localización de ADHOC (`l10n_ar_edi_ux`) que completa el
# contacto desde el padrón de ARCA. Es el mismo que llama el botón «Update
# From AFIP» de la ficha del contacto.
PADRON_METHOD = "button_update_partner_data_from_afip"


class ExpedientSupplierCuitWizard(models.TransientModel):
    """Agregar un proveedor recomendado escribiendo su CUIT.

    Busca el contacto por CUIT y lo suma a los proveedores del expediente o de
    la línea. Si no existe, lo crea con los datos del padrón de ARCA. Es el
    único camino por el que un usuario de Expedientes crea un contacto: el
    permiso sobre Contactos no se toca, la creación corre con `sudo` y solo
    prospera si el padrón devolvió datos —nunca se crea un contacto con el
    CUIT como único dato—.
    """

    _name = "fund.expedient.supplier.cuit.wizard"
    _description = "Agregar proveedor recomendado por CUIT"

    res_model = fields.Selection(
        selection=[
            ("fund.expedient", "Expediente"),
            ("fund.expedient.line", "Línea de expediente"),
        ],
        required=True,
        default=lambda self: self.env.context.get("active_model"),
    )
    res_id = fields.Integer(
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    expedient_id = fields.Many2one(
        "fund.expedient",
        compute="_compute_expedient_id",
        string="Expediente",
    )
    cuit = fields.Char(string="CUIT")
    state = fields.Selection(
        selection=[
            ("search", "Buscar"),
            ("found", "Encontrado en Contactos"),
            ("missing", "No existe en Contactos"),
            ("created", "Creado desde ARCA"),
        ],
        default="search",
        readonly=True,
    )
    partner_id = fields.Many2one("res.partner", string="Contacto", readonly=True)
    partner_vat = fields.Char(related="partner_id.vat", string="CUIT del contacto")
    partner_address = fields.Char(
        compute="_compute_partner_address", string="Domicilio"
    )
    message = fields.Char(readonly=True)
    padron_available = fields.Boolean(compute="_compute_padron_available")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("res_model", "res_id")
    def _compute_expedient_id(self):
        for wizard in self:
            target = wizard._target()
            wizard.expedient_id = (
                target if wizard.res_model == "fund.expedient" else target.expedient_id
            )

    @api.depends("partner_id")
    def _compute_partner_address(self):
        for wizard in self:
            # `sudo`: el usuario puede no tener acceso al contacto y acá solo se
            # muestra para que confirme que es el proveedor correcto.
            wizard.partner_address = (
                wizard.partner_id.sudo()._display_address(without_company=True)
                .replace("\n", ", ")
                if wizard.partner_id
                else False
            )

    def _compute_padron_available(self):
        available = hasattr(self.env["res.partner"], PADRON_METHOD)
        for wizard in self:
            wizard.padron_available = available

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

    def _clean_cuit(self):
        self.ensure_one()
        digits = self._cuit_digits(self.cuit)
        if not digits:
            raise UserError(_("Ingrese un CUIT."))
        if not self._cuit_is_valid(digits):
            raise UserError(
                _("El CUIT %s no es válido: revise los dígitos.") % (self.cuit or "")
            )
        return digits

    @api.model
    def _find_partner(self, digits):
        """Contacto con ese CUIT, prefiriendo la empresa sobre sus contactos.

        El CUIT puede estar guardado con o sin guiones; la localización además
        expone `l10n_ar_vat` ya normalizado cuando está instalada.
        """
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)
        domain = ["|", ("vat", "=", digits), ("vat", "=", self._cuit_format(digits))]
        if "l10n_ar_vat" in Partner._fields:
            domain = ["|", ("l10n_ar_vat", "=", digits)] + domain
        partners = Partner.search(domain)
        if not partners:
            return Partner.browse()
        commercial = partners.mapped("commercial_partner_id")
        return (commercial or partners).sorted(
            key=lambda p: (not p.is_company, not p.active, p.id)
        )[:1]

    # ------------------------------------------------------------------
    # Destino y permisos
    # ------------------------------------------------------------------

    def _target(self):
        self.ensure_one()
        if self.res_model not in TARGET_MODELS or not self.res_id:
            return self.env["fund.expedient"]
        return self.env[self.res_model].browse(self.res_id).exists()

    def _check_target_access(self):
        """Quien agrega tiene que poder editar el expediente en su etapa.

        Se verifica con el usuario real antes de cualquier `sudo`: el asistente
        escribe el contacto y la relación por encima de los permisos, así que
        el permiso funcional se exige acá.
        """
        self.ensure_one()
        target = self._target()
        if not target:
            raise UserError(_("El registro al que se quería agregar el proveedor ya no existe."))
        if not self.env.user.has_group("fund_expedient.group_fund_expedient_user"):
            raise AccessError(_("Solo los usuarios de Expedientes pueden agregar proveedores."))
        expedient = target if self.res_model == "fund.expedient" else target.expedient_id
        if expedient and not expedient.can_edit_in_stage:
            raise AccessError(
                _(
                    "Solo los usuarios asignados a la etapa «%s» pueden modificar los "
                    "proveedores de este expediente."
                )
                % (expedient.stage_id.name or "")
            )
        return target

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    @api.onchange("cuit")
    def _onchange_cuit(self):
        """Resultado instantáneo al escribir: encontrado o no."""
        self.partner_id = False
        self.state = "search"
        self.message = False
        digits = self._cuit_digits(self.cuit)
        if len(digits) < 11:
            return
        if not self._cuit_is_valid(digits):
            self.message = _("El CUIT no es válido: revise los dígitos.")
            return
        partner = self._find_partner(digits)
        if partner:
            self.partner_id = partner
            self.state = "found"
            if not partner.active:
                self.message = _("El contacto está archivado; se agregará igual.")
        else:
            self.state = "missing"
            self.message = (
                _("Se puede crear con los datos del padrón de ARCA.")
                if self.padron_available
                else _(
                    "La localización de ARCA (l10n_ar_edi_ux) no está instalada: "
                    "el contacto debe crearse desde Contactos."
                )
            )

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar proveedor por CUIT"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _add_partner(self, partner):
        target = self._check_target_access()
        if partner in target.recommended_supplier_ids:
            raise UserError(
                _("%s ya figura entre los proveedores recomendados.") % partner.display_name
            )
        # Escritura con el usuario real: los candados de etapa y de validación
        # del expediente aplican igual que si agregara el tag a mano.
        target.write({"recommended_supplier_ids": [(4, partner.id)]})
        return target

    def action_add(self):
        self.ensure_one()
        digits = self._clean_cuit()
        partner = self.partner_id or self._find_partner(digits)
        if not partner:
            raise UserError(_("No hay un contacto con el CUIT %s.") % self._cuit_format(digits))
        self._add_partner(partner)
        return {"type": "ir.actions.act_window_close"}

    def action_add_and_continue(self):
        self.ensure_one()
        digits = self._clean_cuit()
        partner = self.partner_id or self._find_partner(digits)
        if not partner:
            raise UserError(_("No hay un contacto con el CUIT %s.") % self._cuit_format(digits))
        self._add_partner(partner)
        self.write(
            {
                "cuit": False,
                "partner_id": False,
                "state": "search",
                "message": _("%s agregado. Ingrese el siguiente CUIT.") % partner.display_name,
            }
        )
        return self._reopen()

    def action_reset(self):
        """Volver a la búsqueda para cargar otro CUIT, sin agregar nada."""
        self.ensure_one()
        self.write({"cuit": False, "partner_id": False, "state": "search", "message": False})
        return self._reopen()

    def action_create_from_padron(self):
        """Crea el contacto desde el padrón de ARCA y lo agrega."""
        self.ensure_one()
        digits = self._clean_cuit()
        # Permisos primero: la creación corre con sudo.
        self._check_target_access()
        partner = self._find_partner(digits)
        if not partner:
            partner = self._create_partner_from_padron(digits)
        self._add_partner(partner)
        self.write({"partner_id": partner.id, "state": "created", "message": False})
        return self._reopen()

    def _create_partner_from_padron(self, digits):
        """Contacto nuevo con los datos del padrón; sin datos, no se crea.

        Se crea un contacto mínimo (CUIT, tipo de identificación, país) y se
        lo completa con el método de la localización. Todo dentro de un
        savepoint: si el padrón falla o no devuelve nada, no queda ningún
        contacto a medio cargar.
        """
        Partner = self.env["res.partner"].sudo()
        if not hasattr(Partner, PADRON_METHOD):
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
                expedient=self.expedient_id.number or "",
            ),
            subtype_xmlid="mail.mt_note",
        )
        return partner
