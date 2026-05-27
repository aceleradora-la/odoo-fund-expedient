/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Evita error JS en /my si el backend devuelve un contador sin nodo en DOM.
 */
publicWidget.registry.PortalHomeCounters.include({
    async _updateCounters() {
        const needed = [
            ...this.el.querySelectorAll("[data-placeholder_count]"),
        ].map((el) => el.dataset.placeholder_count);
        if (!needed.length) {
            this.el.querySelector(".o_portal_doc_spinner")?.remove();
            return;
        }
        const numberRpc = Math.min(Math.ceil(needed.length / 5), 3);
        const counterByRpc = Math.ceil(needed.length / numberRpc);
        const { rpc } = await import("@web/core/network/rpc");

        const proms = [...Array(Math.min(numberRpc, needed.length)).keys()].map(
            async (i) => {
                const documentsCountersData = await rpc("/my/counters", {
                    counters: needed.slice(
                        i * counterByRpc,
                        (i + 1) * counterByRpc
                    ),
                });
                Object.keys(documentsCountersData).forEach((counterName) => {
                    const documentsCounterEl = this.el.querySelector(
                        `[data-placeholder_count='${counterName}']`
                    );
                    if (!documentsCounterEl) {
                        return;
                    }
                    documentsCounterEl.textContent =
                        documentsCountersData[counterName];
                    if (
                        documentsCountersData[counterName] !== 0 ||
                        this._getCountersAlwaysDisplayed().includes(
                            counterName
                        )
                    ) {
                        documentsCounterEl
                            .closest(".o_portal_index_card")
                            ?.classList.remove("d-none");
                    }
                });
                return documentsCountersData;
            }
        );
        await Promise.all(proms);
        this.el.querySelector(".o_portal_doc_spinner")?.remove();
    },
});
