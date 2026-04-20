/** @odoo-module **/

import { Component, onMounted } from "@odoo/owl";
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

        onMounted(async () => {
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
            try {
                // open() es async: resolve cuando el visor se cierra.
                await this.fileViewer.open(preview);
            } finally {
                document.body.classList.remove("o_fund_expedient_no_download");
            }
            // Volver a la pantalla anterior para evitar quedarse en blanco.
            // restore() vuelve al action previo cuando este componente fue abierto como client action.
            await this.actionService.restore();
        });
    }
}

FundExpedientDocumentFileViewer.template = "fund_expedient.DocumentFileViewer";

registry.category("actions").add("fund_expedient.document_file_viewer", FundExpedientDocumentFileViewer);

