/** @odoo-module **/

import { Component, onWillUnmount, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";

class FundExpedientDocumentFileViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.mailStore = useService("mail.store");
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
            this.fileViewer.open(preview);
        });

        onWillUnmount(() => {
            document.body.classList.remove("o_fund_expedient_no_download");
        });
    }
}

registry.category("actions").add("fund_expedient.document_file_viewer", FundExpedientDocumentFileViewer);

