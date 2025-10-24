# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    # Campo para formato de cheque específico
    l10n_ec_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque',
        domain="[('bank_id', '=', bank_id), ('active', '=', True)]",
        help='Formato específico de cheque para este diario. '
             'Si no se especifica, se usará el formato por defecto del banco.'
    )
    
    @api.onchange('bank_id')
    def _onchange_bank_id_check_format(self):
        """Limpiar formato de cheque si cambia el banco"""
        if self.bank_id and self.l10n_ec_check_format_id:
            if self.l10n_ec_check_format_id.bank_id != self.bank_id:
                self.l10n_ec_check_format_id = False
    
    def get_check_format(self):
        """Obtener el formato de cheque para este diario"""
        self.ensure_one()
        
        # Prioridad 1: Formato específico del diario
        if self.l10n_ec_check_format_id and self.l10n_ec_check_format_id.active:
            return self.l10n_ec_check_format_id
        
        # Prioridad 2: Formato de la cuenta bancaria asociada al diario
        if self.bank_account_id and self.bank_account_id.l10n_ec_check_format_id:
            if self.bank_account_id.l10n_ec_check_format_id.active:
                return self.bank_account_id.l10n_ec_check_format_id
        
        # Prioridad 3: Formato por defecto del banco
        if self.bank_id and self.bank_id.default_check_format_id:
            return self.bank_id.default_check_format_id
        
        # Si no hay formato, retornar False
        return False
