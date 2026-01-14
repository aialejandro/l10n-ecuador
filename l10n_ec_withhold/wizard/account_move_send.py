from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _l10n_ec_is_withhold_move(self, move):
        """Return True if this move is an Ecuadorian withholding document."""
        # Prefer the helper from l10n_ec_withhold if present.
        is_withhold = getattr(move, "is_withhold", None)
        if callable(is_withhold):
            try:
                return bool(is_withhold())
            except Exception:
                return False

        # Fallback: infer from LATAM document type.
        doc_type = getattr(move, "l10n_latam_document_type_id", None)
        internal_type = getattr(doc_type, "internal_type", None)
        return internal_type == "withhold" and getattr(move, "country_code", None) == "EC"

    @api.model
    def _check_move_constrains(self, moves):
        """Allow generating documents for withholds as well as sales documents."""
        if any(move.state != "posted" for move in moves):
            raise UserError(_("You can't generate invoices that are not posted."))

        invalid_moves = moves.filtered(
            lambda m: not m.is_sale_document(include_receipts=True) and not self._l10n_ec_is_withhold_move(m)
        )
        if invalid_moves:
            raise UserError(_("You can only generate sales documents."))

    @api.model
    def _get_placeholder_mail_template_dynamic_attachments_data(self, move, mail_template, pdf_report=None):
        """Prevent duplicate withhold PDFs.

        When the mail template contains report templates, the send wizard will create extra placeholders
        like "withholding ec_<filename>.pdf". For withholds, the PDF is already produced by the wizard
        (see `_prepare_invoice_pdf_report` override), so we remove those extra placeholders.
        """
        withhold_template = self.env.ref('l10n_ec_withhold.email_template_edi_withhold', raise_if_not_found=False)
        if withhold_template and mail_template and mail_template.id == withhold_template.id and self._l10n_ec_is_withhold_move(move):
            return []
        return super()._get_placeholder_mail_template_dynamic_attachments_data(move, mail_template, pdf_report=pdf_report)

    def _prepare_invoice_pdf_report(self, invoices_data):
        """Prepare the pdf report for the invoices passed as parameter.
        :param invoices_data:   A dictionary mapping account.move records to their collected data.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # Log initial invoice data for debugging
        _logger.info(f"=== _prepare_invoice_pdf_report called with {len(invoices_data)} invoices ===")
        for invoice, invoice_data in invoices_data.items():
            _logger.info(f"Invoice {invoice.id}: {invoice.name}, Type: {invoice.move_type}, "
                        f"Document Type: {invoice.l10n_latam_document_type_id.internal_type if invoice.l10n_latam_document_type_id else 'None'}, "
                        f"Currency: {invoice.currency_id.name if invoice.currency_id else 'None'}, "
                        f"Tax Totals: {bool(getattr(invoice, 'tax_totals', None))}")
        
        # If there are ANY withholding invoices in the batch, handle ALL invoices manually
        # to avoid the problematic template processing
        has_withholdings = False
        for invoice, invoice_data in invoices_data.items():
            if (hasattr(invoice, 'l10n_latam_document_type_id') and 
                invoice.l10n_latam_document_type_id and
                invoice.l10n_latam_document_type_id.internal_type == 'withhold'):
                has_withholdings = True
                break
            if hasattr(invoice, 'is_purchase_withhold') and invoice.is_purchase_withhold():
                has_withholdings = True
                break
            if hasattr(invoice, 'is_sale_withhold') and invoice.is_sale_withhold():
                has_withholdings = True
                break
        
        if has_withholdings:
            _logger.info("=== WITHHOLDING DETECTED: Processing ALL invoices manually ===")
            # Process each invoice individually to avoid template conflicts
            for invoice, invoice_data in invoices_data.items():
                if invoice.invoice_pdf_report_id:
                    _logger.info(f"Skipping invoice {invoice.id} - already has PDF")
                    continue
                
                # Check if it's a withholding invoice
                is_withhold = False
                try:
                    if hasattr(invoice, 'is_purchase_withhold') and invoice.is_purchase_withhold():
                        is_withhold = True
                    elif hasattr(invoice, 'is_sale_withhold') and invoice.is_sale_withhold():
                        is_withhold = True
                    elif (hasattr(invoice, 'l10n_latam_document_type_id') and 
                          invoice.l10n_latam_document_type_id and
                          invoice.l10n_latam_document_type_id.internal_type == 'withhold'):
                        is_withhold = True
                except Exception as e:
                    _logger.warning(f"Error checking if invoice {invoice.id} is withhold: {e}")
                    is_withhold = False
                
                try:
                    if is_withhold:
                        _logger.info(f"Processing WITHHOLDING invoice {invoice.id}")
                        # Use withholding-specific report
                        ActionReport = self.env["ir.actions.report"]
                        report_idxml = "l10n_ec_withhold.action_report_withholding_ec"
                        
                        # Add company context to ensure proper currency handling
                        invoice_with_context = invoice.with_context(
                            default_currency_id=invoice.company_id.currency_id.id,
                            company_id=invoice.company_id.id
                        )
                        
                        content, _report_format = ActionReport.with_context(
                            company_id=invoice.company_id.id
                        )._render(report_idxml, [invoice_with_context.id])
                        
                    else:
                        _logger.info(f"Processing REGULAR invoice {invoice.id}")
                        # For regular invoices, use the default report directly
                        pdf_report = invoice_data.get('pdf_report')
                        if not pdf_report:
                            pdf_report = invoice.partner_id.with_company(invoice.company_id).invoice_template_pdf_report_id or self.env.ref('account.account_invoices')
                        
                        ActionReport = self.env["ir.actions.report"]
                        content, _report_format = ActionReport.with_company(invoice.company_id)._render(
                            pdf_report.report_name, 
                            [invoice.id]
                        )
                    
                    # Set the PDF content
                    invoice_data["pdf_attachment_values"] = {
                        "raw": content,
                        "name": invoice._get_invoice_report_filename(),
                        "mimetype": "application/pdf",
                        "res_model": invoice._name,
                        "res_id": invoice.id,
                        "res_field": "invoice_pdf_report_file",  # Binary field
                    }
                    _logger.info(f"Successfully generated report for invoice {invoice.id}")
                    
                except Exception as e:
                    _logger.error(f"Error generating report for invoice {invoice.id}: {e}")
                    invoice_data.setdefault('error', str(e))
        else:
            _logger.info("=== NO WITHHOLDINGS: Using parent method ===")
            # No withholdings in this batch, safe to use parent method
            return super()._prepare_invoice_pdf_report(invoices_data)
