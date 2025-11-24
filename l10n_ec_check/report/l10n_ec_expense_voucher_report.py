# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.tools.misc import format_amount, format_date, formatLang as tools_format_lang

from ..models.amount_to_text import number_to_text_es


class ReportExpenseVoucher(models.AbstractModel):
    _name = 'report.l10n_ec_check.report_expense_voucher'
    _description = 'Comprobante de Egreso - Ecuador'

    @api.model
    def _get_report_values(self, docids, data=None):
        checks = self.env['l10n_latam.check'].browse(docids)
        report_data = {}

        for check in checks:
            payment = check.payment_id
            company = payment.company_id if payment else False
            currency = payment.currency_id if payment and payment.currency_id else (company.currency_id if company else False)
            currency_name = currency.name if currency else 'USD'
            amount = check.amount or 0.0
            amount_in_words = number_to_text_es(amount, currency=currency_name)

            move_lines = payment.move_id.line_ids if payment and payment.move_id else self.env['account.move.line']
            # Sort lines to keep liquidity vs expense grouped but deterministic
            move_lines = move_lines.sorted(key=lambda l: ((l.account_id.code or ''), l.id)) if move_lines else move_lines
            total_debit = sum(move_lines.mapped('debit')) if move_lines else 0.0
            total_credit = sum(move_lines.mapped('credit')) if move_lines else 0.0

            partner = payment.partner_id if payment else check.partner_id
            report_data[check.id] = {
                'partner_name': partner.display_name if partner else '',
                'partner_vat': partner.vat if partner else '',
                'check_number': check.name or '',
                'amount': amount,
                'amount_in_words': amount_in_words,
                'amount_formatted': format_amount(self.env, amount, currency) if currency else f"{amount:0.2f}",
                'payment_memo': payment.memo if payment else '',
                'payment_ref': payment.memo if payment else '',
                'payment_name': payment.name if payment else '',
                'payment_date': payment.date if payment else False,
                'payment_creator': payment.create_uid.display_name if payment and payment.create_uid else '',
                'company': company,
                'currency': currency,
                'move_lines': move_lines,
                'move_name': payment.move_id.name if payment and payment.move_id else '',
                'total_debit': total_debit,
                'total_credit': total_credit,
            }

        return {
            'doc_ids': docids,
            'doc_model': 'l10n_latam.check',
            'docs': checks,
            'report_data': report_data,
            'format_date': lambda value: format_date(self.env, value) if value else '',
            'format_amount': lambda amount, currency: format_amount(self.env, amount, currency) if currency else amount,
            'formatLang': lambda *args, **kwargs: tools_format_lang(self.env, *args, **kwargs),
        }
