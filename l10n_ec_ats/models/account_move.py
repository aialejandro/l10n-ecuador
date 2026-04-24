from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ec_get_ats_latam_document_type_code(self):
        self.ensure_one()
        doc_type_code = self.l10n_latam_document_type_id.code
        if not doc_type_code and getattr(self, "l10n_ec_withholding_type", False) == "purchase":
            doc_type_code = "07"
        return doc_type_code

    def _l10n_ec_get_ats_authorization_number(self):
        self.ensure_one()
        return (
            (getattr(self, "l10n_ec_electronic_authorization", False) or "").strip()
            or (getattr(self, "l10n_ec_legacy_document_authorization", False) or "").strip()
            or (getattr(self, "l10n_ec_xml_access_key", False) or "").strip()
            or ""
        )
