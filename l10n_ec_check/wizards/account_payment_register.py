# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command


class L10nEcPaymentRegisterCheck(models.TransientModel):
    _inherit = 'l10n_latam.payment.register.check'

    beneficiary = fields.Char(string='Beneficiario')

    @api.onchange('payment_register_id.partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.beneficiary or not record.payment_register_id.partner_id:
                continue
            record.beneficiary = record.payment_register_id.partner_id.name


class L10nEcAccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payment_vals_from_wizard(self, batch_result):
        self.ensure_one()
        vals = super()._create_payment_vals_from_wizard(batch_result)
        commands = vals.get('l10n_latam_new_check_ids')
        if commands:
            new_commands = []
            wizard_lines = list(self.l10n_latam_new_check_ids)
            for idx, command in enumerate(commands):
                if isinstance(command, (list, tuple)) and len(command) == 3 and command[0] == Command.CREATE:
                    command_vals = dict(command[2]) if command[2] else {}
                    beneficiary = False
                    if idx < len(wizard_lines):
                        wizard_line = wizard_lines[idx]
                        beneficiary = wizard_line.beneficiary or wizard_line.payment_register_id.partner_id.name
                    if beneficiary and not command_vals.get('beneficiary'):
                        command_vals['beneficiary'] = beneficiary
                    new_commands.append(Command.create(command_vals))
                else:
                    new_commands.append(command)
            vals['l10n_latam_new_check_ids'] = new_commands
        return vals