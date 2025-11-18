# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    def get_check_format(self):
        """Obtener el formato de cheque para este diario"""
        self.ensure_one()
        
        # Prioridad 1: Formato de la cuenta bancaria asociada al diario
        if self.bank_account_id and self.bank_account_id.l10n_ec_check_format_id:
            if self.bank_account_id.l10n_ec_check_format_id.active:
                return self.bank_account_id.l10n_ec_check_format_id
        
        # Prioridad 2: Formato por defecto del banco
        if self.bank_id and self.bank_id.default_check_format_id:
            return self.bank_id.default_check_format_id
        
        # Si no hay formato, retornar False
        return False
