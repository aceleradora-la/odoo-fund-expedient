/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useRef, useState } from "@odoo/owl";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

/**
 * Proveedores recomendados, cargados por CUIT.
 *
 * Reemplaza el autocompletado del many2many_tags por un cuadro donde se
 * escribe el CUIT: al completar los 11 dígitos busca el contacto y lo agrega
 * como burbuja. Si no existe, ofrece crearlo desde el padrón de ARCA. Las
 * burbujas y su cruz para quitar son las del widget estándar.
 */
export class SupplierCuitTagsField extends Many2ManyTagsField {
    static template = "fund_expedient.SupplierCuitTagsField";

    setup() {
        super.setup();
        this.inputRef = useRef("cuitInput");
        this.state = useState({
            message: "",
            kind: "",
            canCreate: false,
            busy: false,
            lastCuit: "",
        });
    }

    /** Expediente al que pertenece el campo (directo o vía la línea). */
    get expedientId() {
        const record = this.props.record;
        if (record.resModel === "fund.expedient") {
            return record.resId || false;
        }
        const expedient = record.data.expedient_id;
        if (Array.isArray(expedient) && expedient[0]) {
            return expedient[0];
        }
        const parent = record.evalContext && record.evalContext.parent;
        return (parent && parent.id) || false;
    }

    get messageClass() {
        return {
            success: "text-success",
            warning: "text-warning",
            error: "text-danger",
        }[this.state.kind] || "text-muted";
    }

    digits(value) {
        return (value || "").replace(/\D/g, "");
    }

    currentIds() {
        return this.props.record.data[this.props.name].currentIds;
    }

    setMessage(message, kind) {
        this.state.message = message || "";
        this.state.kind = kind || "";
    }

    clearInput() {
        if (this.inputRef.el) {
            this.inputRef.el.value = "";
        }
    }

    async onInput(ev) {
        const cuit = this.digits(ev.target.value);
        if (cuit.length === 11) {
            await this.lookup(cuit);
        } else if (this.state.message) {
            this.setMessage("", "");
            this.state.canCreate = false;
        }
    }

    async onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            await this.lookup(this.digits(ev.target.value));
        }
    }

    async lookup(cuit) {
        if (!cuit || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.canCreate = false;
        try {
            const result = await this.orm.call(
                "fund.expedient.supplier.cuit",
                "find_partner_by_cuit",
                [cuit]
            );
            if (!result.valid) {
                this.setMessage(result.message, "error");
                return;
            }
            if (result.found) {
                await this.addPartner(result.partner, result.message);
                return;
            }
            this.state.lastCuit = cuit;
            this.state.canCreate = Boolean(result.padron_available);
            this.setMessage(result.message, "warning");
        } finally {
            this.state.busy = false;
        }
    }

    async addPartner(partner, extraMessage) {
        if (this.currentIds().includes(partner.id)) {
            this.setMessage(
                _t("%s ya figura entre los proveedores recomendados.", partner.display_name),
                "warning"
            );
            this.clearInput();
            return;
        }
        await this.update([partner]);
        const message = _t("Agregado: %s", partner.display_name);
        this.setMessage(extraMessage ? `${message} ${extraMessage}` : message, "success");
        this.clearInput();
    }

    async onCreate(ev) {
        ev.preventDefault();
        if (!this.state.lastCuit || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const partner = await this.orm.call(
                "fund.expedient.supplier.cuit",
                "create_partner_from_cuit",
                [this.state.lastCuit, this.expedientId]
            );
            this.state.canCreate = false;
            await this.addPartner(partner);
            this.setMessage(
                _t("Creado desde ARCA y agregado: %s", partner.display_name),
                "success"
            );
        } finally {
            this.state.busy = false;
        }
    }
}

export const supplierCuitTagsField = {
    ...many2ManyTagsField,
    component: SupplierCuitTagsField,
};

registry.category("fields").add("fund_supplier_cuit_tags", supplierCuitTagsField);
