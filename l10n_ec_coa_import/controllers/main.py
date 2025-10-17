from pathlib import Path

from odoo import http
from odoo.http import content_disposition, request
from odoo.modules.module import get_module_resource


class L10nEcCoaImportController(http.Controller):
    @http.route(
        "/l10n_ec_coa_import/template/download",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download_template(self, **_kwargs):
        resource_path = get_module_resource(
            "l10n_ec_coa_import",
            "static",
            "template",
            "l10n_ec_coa_template.xlsx",
        )
        if not resource_path:
            return request.not_found()
        data = Path(resource_path).read_bytes()
        return request.make_response(
            data,
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition("l10n_ec_coa_template.xlsx")),
            ],
        )
