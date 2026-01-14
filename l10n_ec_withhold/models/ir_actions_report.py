# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError
from odoo import _


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # Check for reports only available for invoices.
        # Allow withholding moves to bypass the entry-only restriction.
        if self._is_invoice_report(report_ref):
            invoices = self.env['account.move'].browse(res_ids)
            # Handle display_name_in_footer regardless of document type
            if self.env['ir.config_parameter'].sudo().get_param('account.display_name_in_footer'):
                data = data and dict(data) or {}
                data.update({'display_name_in_footer': True})
            
            # Check if this is a withholding-only batch
            has_entries = any(x.move_type == 'entry' for x in invoices)
            if has_entries:
                all_withhold = all(
                    x.l10n_latam_document_type_id.internal_type == 'withhold'
                    for x in invoices
                    if x.move_type == 'entry'
                )
                if not all_withhold:
                    raise UserError(_("Only invoices could be printed."))
            
            # For withholdings, skip the account module's check and call base directly
            if has_entries and all_withhold:
                from odoo.addons.base.models.ir_actions_report import IrActionsReport as BaseIrActionsReport
                return BaseIrActionsReport._pre_render_qweb_pdf(self, report_ref, res_ids=res_ids, data=data)

        return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
