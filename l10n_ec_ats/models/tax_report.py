from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TaxReport(models.TransientModel):
    _inherit = "tax.report"

    @api.model
    def export_ats_xml_dynamic(self, start_date=None, end_date=None):
        company = self.env.company
        if company.account_fiscal_country_id.code != "EC":
            raise UserError(_("El ATS solo esta disponible para companias con localizacion de Ecuador."))

        date_from = fields.Date.to_date(start_date) if start_date else fields.Date.start_of(fields.Date.today(), "month")
        date_to = fields.Date.to_date(end_date) if end_date else fields.Date.end_of(fields.Date.today(), "month")

        handler = self.env["l10n.ec.ats.helper"]

        options = {
            "date": {
                "date_from": fields.Date.to_string(date_from),
                "date_to": fields.Date.to_string(date_to),
                "string": f"{date_from.strftime('%m/%Y')}",
            }
        }
        xml_content, errors = handler._generate_ats(options)
        if errors:
            raise UserError(
                _("No se pudo generar el ATS por inconsistencias de datos:\n%s") % "\n".join(errors)
            )

        file_name = f"ATS-{date_to.strftime('%Y-%m')}.xml"
        return xml_content, file_name
