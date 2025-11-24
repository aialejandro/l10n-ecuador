# -*- coding: utf-8 -*-

from odoo import models, fields, _, api
from odoo.exceptions import UserError



class L10nEcCheck(models.Model):
    _inherit = 'l10n_latam.check'

    beneficiary = fields.Char(
        string='Beneficiary',
        help='Name of the beneficiary displayed on the check.'
    )
    payment_ref = fields.Char(
        string='Payment Reference',
        related='payment_id.memo',
        store=True,
        readonly=False,
    )
    date = fields.Date(
        string='Issue Date',
        related='payment_id.date',
        store=True,
        readonly=False,
    )
    check_printed = fields.Boolean(
        string='Check Printed',
        default=False,
        copy=False,
        help='Indicates whether the check has already been printed.'
    )
    check_print_date = fields.Datetime(
        string='Check Print Date',
        readonly=True,
        copy=False,
        help='Date and time when the check was printed.'
    )
    check_printed_by = fields.Many2one(
        'res.users',
        string='Printed By',
        readonly=True,
        copy=False,
        help='User who printed the check.'
    )
    check_reprinted = fields.Boolean(
        string='Check Reprinted',
        default=False,
        copy=False,
        help='Indicates whether the check was reset to allow reprinting.'
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'name' in fields_list and not defaults.get('name'):
            payment = self._l10n_ec_get_payment_from_context()
            bank_account = payment._l10n_ec_get_check_bank_account() if payment else self.env['res.partner.bank']
            if bank_account:
                taken_numbers = [name for name in payment.l10n_latam_new_check_ids.mapped('name') if name] if payment else []
                peek_number = bank_account._l10n_ec_peek_next_check_number(taken_numbers)
                if peek_number:
                    defaults['name'] = peek_number
        return defaults

    @api.onchange('payment_id', 'partner_id')
    def _onchange_beneficiary_from_partner(self):
        for record in self:
            partner_name = record.partner_id.name or record.payment_id.partner_id.name
            if partner_name:
                record.beneficiary = partner_name
            elif record.beneficiary:
                record.beneficiary = False

    @api.model_create_multi
    def create(self, vals_list):
        payment_cache = {}
        default_payment_id = self.env.context.get('default_payment_id')
        for vals in vals_list:
            payment_id = vals.get('payment_id') or default_payment_id
            payment = payment_cache.get(payment_id)
            if payment is None and payment_id:
                payment = self.env['account.payment'].browse(payment_id)
                payment_cache[payment_id] = payment
            if payment and payment.partner_id and not vals.get('beneficiary'):
                vals['beneficiary'] = payment.partner_id.name

            bank_account = payment._l10n_ec_get_check_bank_account() if payment else self.env['res.partner.bank']
            if bank_account and payment and payment.payment_method_code == 'own_checks':
                reserved_number = bank_account._l10n_ec_reserve_next_check_number()
                manual_number = vals.get('name')
                if manual_number and str(manual_number).isdigit():
                    manual_int = int(str(manual_number))
                    reserved_int = int(reserved_number)
                    if manual_int > reserved_int:
                        bank_account._l10n_ec_sync_next_number(manual_number)
                        vals['name'] = str(manual_number).zfill(8)
                    elif manual_int == reserved_int:
                        vals['name'] = reserved_number
                    else:
                        vals['name'] = reserved_number
                elif manual_number:
                    vals['name'] = reserved_number
                else:
                    vals['name'] = reserved_number
            elif bank_account and vals.get('name'):
                bank_account._l10n_ec_sync_next_number(vals['name'])
        checks = super().create(vals_list)
        for check in checks.filtered(lambda chk: not chk.beneficiary and chk.partner_id):
            check.beneficiary = check.partner_id.name
        return checks

    def _l10n_ec_get_payment_from_context(self):
        payment = self.env['account.payment']
        payment_id = self.env.context.get('default_payment_id')
        if not payment_id and self.env.context.get('parent_model') == 'account.payment':
            payment_id = self.env.context.get('parent_id')
        if payment_id:
            payment = self.env['account.payment'].browse(payment_id)
        return payment if payment and payment.id else False

    def _l10n_ec_get_bank_account_from_context(self):
        payment = self._l10n_ec_get_payment_from_context()
        if payment:
            return payment._l10n_ec_get_check_bank_account()
        return self.env['res.partner.bank']

    def action_l10n_ec_print_check(self):
        """Execute the Ecuadorian check printing flow for the current checks."""
        self.ensure_one()
        payment = self.payment_id

        if not payment:
            raise UserError(_('The check is not linked to a payment.'))
                
        if self.check_printed:
            raise UserError(_(
                'The check %(payment)s (%(number)s) was already printed.\n\n'
                'To reprint it, use the "Reset Print" button (requires administrator permissions).'
            ) % {
                'payment': payment.name,
                'number': self.name or _('No number'),
            })

        if not payment.l10n_ec_check_format_id:
            journal = payment.journal_id
            bank_account = journal.bank_account_id if journal else False
            bank = journal.bank_id if journal else False
            raise UserError(_(
                'The journal %(journal)s does not have a check format on bank account %(account)s '
                'and bank %(bank)s does not define a default check format.'
            ) % {
                'journal': journal.name if journal else _('No journal'),
                'account': bank_account.display_name if bank_account else _('No bank account'),
                'bank': bank.name if bank else _('No bank'),
            })

        missing_fields = []
        format_fields = payment.l10n_ec_check_format_id.format_field_ids.filtered('is_required')
        for field in format_fields:
            value = field.get_field_value(self)
            if not value:
                missing_fields.append(field.label)

        if missing_fields:
            raise UserError(_(
                'The check %(number)s has mandatory fields missing:\n%(fields)s'
            ) % {
                'number': self.name or _('No number'),
                'fields': '\n'.join(missing_fields),
            })

        now = fields.Datetime.now()
        self.write({
            'check_printed': True,
            'check_print_date': now,
            'check_printed_by': self.env.user.id,
        })

        date_str = fields.Datetime.to_string(now)
        message_body = _(
            'Check %(check_name)s was printed on %(date)s by %(user)s.'
        ) % {
            'check_name': self.display_name,
            'date': date_str,
            'user': self.env.user.display_name,
        }
        payment.message_post(body=message_body, subtype_xmlid='mail.mt_note')
        self.message_post(body=message_body, subtype_xmlid='mail.mt_note')

        return self.env.ref('l10n_ec_check.action_report_check_print').report_action(self)

    def action_l10n_ec_print_expense_voucher(self):
        """Print the expense voucher (comprobante de egreso) for this check."""
        self.ensure_one()
        payment = self.payment_id

        if not payment:
            raise UserError(_('The check is not linked to a payment.'))

        if not payment.move_id:
            raise UserError(_('You can only print the expense voucher once the payment has a journal entry.'))

        return self.env.ref('l10n_ec_check.action_report_expense_voucher').report_action(self)

    def action_l10n_ec_reset_print_state(self):
        """Reset the print status of each check individually."""
        printed_checks = self.filtered('check_printed')
        if not printed_checks:
            return True

        reset_timestamp = fields.Datetime.now()
        reset_timestamp_str = fields.Datetime.to_string(reset_timestamp)
        current_user = self.env.user

        for check in printed_checks:
            payment = check.payment_id
            original_info = '  • %s → %s (%s)' % (
                check.name or _('No number'),
                fields.Datetime.to_string(check.check_print_date) if check.check_print_date else 'N/A',
                check.check_printed_by.name if check.check_printed_by else _('Unknown user')
            )

            message_body = _(
                '⚠️ CHECK PRINT STATUS RESET\n'
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                'Reset by: %s\n'
                'Reset on: %s\n'
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                'Original check data:\n%s\n'
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                '⚠️ Checks can now be reprinted'
            ) % (
                current_user.name,
                reset_timestamp_str,
                original_info or _('No information')
            )

            if payment:
                payment.message_post(
                    body=message_body,
                    subject=_('🔓 Check Print Status Reset'),
                    message_type='notification',
                )
            check.message_post(
                body=message_body,
                subject=_('🔓 Check Print Status Reset'),
                message_type='notification',
            )

        printed_checks.write({
            'check_printed': False,
            'check_print_date': False,
            'check_printed_by': False,
            'check_reprinted': True,
        })

        return True


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _build_wkhtmltopdf_args(
        self,
        paperformat_id,
        landscape,
        specific_paperformat_args=None,
        set_viewport_size=False,
    ):
        args = super()._build_wkhtmltopdf_args(
            paperformat_id,
            landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size,
        )
        if "--encoding" not in args:
            args = ["--encoding", "utf-8"] + args
        return args