# Copyright 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import http
from odoo.http import request


class FundExpedientContentController(http.Controller):
    """Restringe descarga de documentos del expediente por etapa.

    Regla:
    - Si el usuario NO está asignado a la etapa del documento, solo puede previsualizar.
    - Si el usuario está asignado pero el expediente está en otra etapa, solo puede previsualizar.
    - Descarga (attachment) solo si: asignado a la etapa Y documento pertenece a la etapa actual del expediente.
    """

    @http.route("/fund_expedient/document/download/<int:doc_id>", type="http", auth="user")
    def document_download(self, doc_id, **kwargs):
        doc = request.env["fund.expedient.document"].browse(doc_id).exists()
        if not doc:
            return request.not_found()

        # Si no puede descargar, forzamos inline (preview).
        if not doc.can_download_file:
            kwargs = dict(kwargs)
            kwargs["download"] = "0"

        # Delegamos en el handler estándar de Odoo para binarios.
        # Usamos /web/content para respetar mimetype, filename, etc.
        url = f"/web/content/fund.expedient.document/{doc.id}/file_data"
        # Preservar filename
        if doc.file_name:
            url += f"?filename={http.url_quote(doc.file_name)}"
        else:
            url += "?"
        # Param download acorde a la regla
        url += "&download=1" if str(kwargs.get("download", "1")) in ("1", "true", "True") else "&download=0"
        return request.redirect(url)

