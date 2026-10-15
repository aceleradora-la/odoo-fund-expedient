/** @odoo-module **/

import { Component, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";

class FundExpedientDocumentFileViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.mailStore = useService("mail.store");
        this.actionService = useService("action");
        this.fileViewer = useFileViewer();
        const { attachmentId, filename, mimetype, canDownload } = this.props.action.params || {};
        this.attachmentId = attachmentId;
        this.filename = filename;
        this.mimetype = mimetype;
        this.canDownload = !!canDownload;
        this._poll = null;

        onMounted(() => {
            // Ocultar descarga en el visor cuando no corresponde.
            if (!this.canDownload) {
                document.body.classList.add("o_fund_expedient_no_download");
            }
            const preview = this.mailStore.Attachment.insert({
                id: this.attachmentId,
                filename: this.filename,
                name: this.filename,
                mimetype: this.mimetype,
            });
            // open() no siempre es awaitable "hasta el cierre", así que detectamos cierre por DOM.
            this.fileViewer.open(preview);

            // Cuando el visor se cierra, desaparece el contenedor .o-FileViewer.
            this._poll = window.setInterval(async () => {
                const isOpen = !!document.querySelector(".o-FileViewer");
                if (isOpen) return;
                window.clearInterval(this._poll);
                this._poll = null;
                document.body.classList.remove("o_fund_expedient_no_download");
                await this.actionService.restore();
            }, 250);
        });

        onWillUnmount(() => {
            if (this._poll) {
                window.clearInterval(this._poll);
                this._poll = null;
            }
            document.body.classList.remove("o_fund_expedient_no_download");
        });
    }
}

FundExpedientDocumentFileViewer.template = "fund_expedient.DocumentFileViewer";

registry.category("actions").add("fund_expedient.document_file_viewer", FundExpedientDocumentFileViewer);

