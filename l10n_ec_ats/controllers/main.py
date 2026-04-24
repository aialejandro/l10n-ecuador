from odoo import http
from odoo.http import content_disposition, request


class L10nEcAtsController(http.Controller):
    @http.route("/l10n_ec_ats/export_xml", type="http", auth="user", methods=["POST"], csrf=False)
    def export_xml(self, start_date=None, end_date=None, token=None, **kwargs):
        xml_content, file_name = request.env["tax.report"].export_ats_xml_dynamic(
            start_date=start_date,
            end_date=end_date,
        )
        response = request.make_response(
            xml_content,
            headers=[
                ("Content-Type", "application/xml;charset=utf-8"),
                ("Content-Disposition", content_disposition(file_name)),
            ],
        )
        if token:
            response.set_cookie("fileToken", token)
        return response
