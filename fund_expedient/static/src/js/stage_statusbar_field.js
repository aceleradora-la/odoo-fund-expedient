/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    StatusBarField,
    statusBarField,
} from "@web/views/fields/statusbar/statusbar_field";

/**
 * Barra de etapas en el orden del flujo del tipo de expediente.
 *
 * La barra estándar pide las etapas al servidor sin decir de qué expediente
 * se trata, y las recibe en el orden general de las etapas. El orden del
 * flujo, en cambio, es el de la lista de etapas de cada tipo: lo calcula el
 * servidor en `allowed_stage_order` y acá solo se reordena lo que se muestra.
 */
export class FundStageStatusBarField extends StatusBarField {
    getAllItems() {
        const items = super.getAllItems();
        const order = (this.props.record.data.allowed_stage_order || "")
            .split(",")
            .filter(Boolean)
            .map(Number);
        if (!order.length) {
            return items;
        }
        const position = new Map(order.map((stageId, index) => [stageId, index]));
        const rank = (item) => (position.has(item.value) ? position.get(item.value) : order.length);
        return [...items].sort((a, b) => rank(a) - rank(b));
    }
}

export const fundStageStatusBarField = {
    ...statusBarField,
    component: FundStageStatusBarField,
};

registry.category("fields").add("fund_stage_statusbar", fundStageStatusBarField);
