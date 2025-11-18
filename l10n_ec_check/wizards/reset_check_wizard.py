# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from passlib.context import CryptContext


class L10nEcCheckResetWizard(models.TransientModel):
    _name = 'l10n_ec.check.reset.wizard'
    _description = 'Check Print Reset Wizard'

    check_ids = fields.Many2many(
        'l10n_latam.check',
        string='Checks to Reset',
        required=True,
        readonly=True,
        domain="[('check_printed', '=', True)]"
    )

    password = fields.Char(
        string='Administrator Password',
        help='Enter your current password to confirm the reset.'
    )

    check_count = fields.Integer(
        string='Check Count',
        compute='_compute_check_count'
    )

    check_details = fields.Html(
        string='Check Details',
        compute='_compute_check_details'
    )
    reset_warning_html = fields.Html(
        string='Warning Details',
        compute='_compute_reset_warning_html'
    )
    
    @api.depends('check_ids')
    def _compute_check_count(self):
        for wizard in self:
            wizard.check_count = len(wizard.check_ids)
    
    @api.depends('check_ids')
    def _compute_check_details(self):
        for wizard in self:
            if not wizard.check_ids:
                wizard.check_details = '<p>%s</p>' % _('No checks selected')
                continue
            
            headers = [
                _('Check'),
                _('Payment'),
                _('Amount'),
                _('Printed On'),
                _('Printed By'),
            ]

            html = '<table class="table table-sm table-striped">'
            html += '<thead><tr>' + ''.join('<th>%s</th>' % header for header in headers) + '</tr></thead><tbody>'

            for check in wizard.check_ids:
                payment = check.payment_id
                currency = check.currency_id or (payment.currency_id if payment else False)
                symbol = currency.symbol if currency else ''
                amount_value = check.amount or (payment.amount if payment else 0.0)
                payment_name = payment.name if payment else _('N/A')
                check_name = check.name or _('N/A')
                printed_on = check.check_print_date.strftime('%Y-%m-%d %H:%M') if check.check_print_date else _('N/A')
                printed_by = check.check_printed_by.name if check.check_printed_by else _('Unknown user')
                html += '<tr>'
                html += f'<td><strong>{check_name}</strong></td>'
                html += f'<td>{payment_name}</td>'
                html += f'<td>{symbol} {amount_value:,.2f}</td>'
                html += f'<td>{printed_on}</td>'
                html += f'<td>{printed_by}</td>'
                html += '</tr>'
            
            html += '</tbody></table>'
            wizard.check_details = html

    @api.depends('check_ids')
    def _compute_reset_warning_html(self):
        for wizard in self:
            warning_text = _("You are about to reset the print status of <strong>%(count)s checks</strong>. This action allows the checks to be reprinted.") % {'count': wizard.check_count}
            wizard.reset_warning_html = '<p style="margin-top: 8px;">%s</p>' % warning_text
    
    def action_confirm_reset(self):
        """Validate the password and trigger the reset on selected checks."""
        self.ensure_one()
        
        if not self.password:
            raise ValidationError(_('You must enter your password to continue.'))

        current_user = self.env.user

        try:
            uid = self.env['res.users'].sudo().with_context(no_reset_password=True).search([
                ('id', '=', current_user.id),
                ('login', '=', current_user.login)
            ], limit=1)
            
            if not uid:
                raise ValidationError(_('User not found.'))

            self.env.cr.execute(
                "SELECT password FROM res_users WHERE id = %s",
                (current_user.id,)
            )
            result = self.env.cr.fetchone()
            stored_password = result[0] if result else None
            
            if stored_password:
                crypt_context = CryptContext(
                    schemes=['pbkdf2_sha512', 'plaintext'],
                    deprecated=['plaintext']
                )
                valid = crypt_context.verify(self.password, stored_password)
                if not valid:
                    raise ValidationError(_('Incorrect password.'))
            else:
                try:
                    authenticated_uid = self.env['res.users']._authenticate(
                        self.env.cr.dbname,
                        current_user.login,
                        self.password
                    )
                    if authenticated_uid != current_user.id:
                        raise ValidationError(_('Incorrect password.'))
                except Exception:
                    raise ValidationError(_(
                        'The password could not be validated. '
                        'The user might not have a password configured.'
                    ))
                    
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_(
                'Error validating the password: %s'
            ) % str(e))
        
        checks_to_reset = self.check_ids.filtered('check_printed')
        if not checks_to_reset:
            raise ValidationError(_('No printed checks were selected.'))

        checks_to_reset.action_l10n_ec_reset_print_state()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(
                    'The print status of %d check(s) was reset. '
                    'They can now be reprinted.'
                ) % len(checks_to_reset),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }
    
    def action_cancel(self):
        """Close the wizard without applying changes."""
        return {'type': 'ir.actions.act_window_close'}
