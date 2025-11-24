# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    l10n_ec_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Check Format',
        compute='_compute_l10n_ec_check_format_id',
        store=True,
        readonly=False,
        help='Check format used to print this payment.'
    )
    l10n_ec_single_check_available = fields.Boolean(
        string='Single Check Available',
        compute='_compute_l10n_ec_single_check_available',
        store=True,
        help='Indicates if there is exactly one check to allow direct printing from the payment.'
    )
    l10n_ec_single_check_printed = fields.Boolean(
        string='Single Check Printed',
        compute='_compute_l10n_ec_single_check_printed',
        store=True,
        help='Indicates if the single check linked to this payment was already printed.'
    )
    
    @api.depends('journal_id',
                 'journal_id.bank_account_id', 'journal_id.bank_account_id.l10n_ec_check_format_id',
                 'journal_id.bank_id', 'journal_id.bank_id.default_check_format_id',
                 'payment_method_code')
    def _compute_l10n_ec_check_format_id(self):
        """Retrieve the check format based on the journal."""
        for payment in self:
            payment.l10n_ec_check_format_id = False
            if payment.payment_method_code != 'own_checks' or not payment.journal_id:
                continue
            check_format = payment.journal_id.get_check_format()
            if check_format:
                payment.l10n_ec_check_format_id = check_format

    @api.depends('payment_method_code', 'l10n_latam_new_check_ids')
    def _compute_l10n_ec_single_check_available(self):
        """Only allow direct printing when there is exactly one check."""
        for payment in self:
            payment.l10n_ec_single_check_available = (
                payment.payment_method_code == 'own_checks'
                and len(payment.l10n_latam_new_check_ids) == 1
            )

    @api.depends('l10n_latam_new_check_ids', 'l10n_latam_new_check_ids.check_printed')
    def _compute_l10n_ec_single_check_printed(self):
        """Track whether the single available check was already printed."""
        for payment in self:
            payment.l10n_ec_single_check_printed = bool(payment.l10n_latam_new_check_ids.filtered('check_printed'))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure a check format is assigned."""
        payments = super().create(vals_list)
        # Force recomputation of the format for check payments
        check_payments = payments.filtered(lambda p: p.payment_method_code == 'own_checks')
        if check_payments:
            check_payments._compute_l10n_ec_check_format_id()
        return payments

    def write(self, vals):
        """Override write to recompute the format if the journal or method changes."""
        result = super().write(vals)
        # Recompute the format if journal or payment method changed
        if 'journal_id' in vals or 'payment_method_code' in vals or 'payment_method_line_id' in vals:
            check_payments = self.filtered(lambda p: p.payment_method_code == 'own_checks')
            if check_payments:
                check_payments._compute_l10n_ec_check_format_id()
        return result

    @api.onchange('partner_id', 'l10n_latam_new_check_ids')
    def _onchange_l10n_ec_check_beneficiary(self):
         for payment in self:
            partner_name = payment.partner_id.name or False
            for check in payment.l10n_latam_new_check_ids:
                if partner_name and check.beneficiary != partner_name:
                    check.beneficiary = partner_name
                elif not partner_name and check.beneficiary:
                    check.beneficiary = False
    
    def action_print_check(self):
        self.ensure_one()

        if not self.l10n_ec_single_check_available:
            raise UserError(_(
                'Printing from the payment is only available when there is a single check.\n'
                'Print each check individually from the list.'
            ))

        return self.l10n_latam_new_check_ids.action_l10n_ec_print_check()
    
    def action_reset_check_printed(self):
        """Open a wizard to reset the check print state.
        Requires the current user's password confirmation."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Only system administrators can reset the check print status.'
            ))

        printed_checks = self.mapped('l10n_latam_new_check_ids').filtered('check_printed')
        if not printed_checks:
            raise UserError(_('The selected payments do not have printed checks.'))

        return {
            'name': _('Reset Checks Print Status'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_ec.check.reset.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_check_ids': [(6, 0, printed_checks.ids)],
            }
        }

    def _l10n_ec_get_check_bank_account(self):
        """Return the bank account that controls numbering for own checks."""
        self.ensure_one()
        if self.payment_method_code != 'own_checks' or not self.journal_id:
            return self.env['res.partner.bank']
        return self.journal_id.bank_account_id