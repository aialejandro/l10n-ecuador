# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'
    
    l10n_ec_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque',
        domain="['|', ('bank_id', '=', False), ('bank_id', '=', bank_id), ('active', '=', True)]",
        help='Formato de cheque a utilizar para esta cuenta bancaria.\n'
             'Este formato se usará automáticamente cuando se impriman cheques '
             'desde diarios asociados a esta cuenta.\n'
             'Se muestran formatos del banco seleccionado o formatos genéricos.'
    )
    
    # Control de numeración de cheques
    l10n_ec_check_next_number = fields.Integer(
        string='Siguiente Número de Cheque',
        default=1,
        help='Próximo número de cheque a utilizar. Se incrementa automáticamente al imprimir.'
    )
    
    l10n_ec_check_last_number = fields.Char(
        string='Último Cheque Impreso',
        readonly=True,
        compute='_compute_last_check_number',
        help='Número del último cheque impreso desde esta cuenta'
    )
    
    l10n_ec_total_checks_printed = fields.Integer(
        string='Total Cheques Impresos',
        compute='_compute_checks_statistics',
        help='Cantidad total de cheques impresos desde esta cuenta'
    )
    
    @api.depends('acc_number')
    def _compute_last_check_number(self):
        """Obtener el último número de cheque impreso"""
        Check = self.env['l10n_latam.check']
        for bank_account in self:
            last_check = Check.search([
                ('payment_id.journal_id.bank_account_id', '=', bank_account.id),
                ('payment_id.payment_method_code', '=', 'own_checks'),
                ('check_printed', '=', True),
                ('name', '!=', False),
            ], order='check_print_date desc', limit=1)

            bank_account.l10n_ec_check_last_number = last_check.name if last_check else ''
    
    @api.depends('acc_number')
    def _compute_checks_statistics(self):
        """Calcular estadísticas de cheques"""
        Check = self.env['l10n_latam.check']
        for bank_account in self:
            checks_count = Check.search_count([
                ('payment_id.journal_id.bank_account_id', '=', bank_account.id),
                ('payment_id.payment_method_code', '=', 'own_checks'),
                ('check_printed', '=', True)
            ])
            bank_account.l10n_ec_total_checks_printed = checks_count
    
    @api.onchange('bank_id')
    def _onchange_bank_id(self):
        """Al cambiar el banco, intentar asignar el formato por defecto"""
        if self.bank_id:
            if self.bank_id.default_check_format_id:
                self.l10n_ec_check_format_id = self.bank_id.default_check_format_id
            else:
                self.l10n_ec_check_format_id = False
        else:
            self.l10n_ec_check_format_id = False
    
    @api.constrains('l10n_ec_check_next_number')
    def _check_next_number_positive(self):
        """Validar que el siguiente número sea positivo"""
        for bank_account in self:
            if bank_account.l10n_ec_check_next_number < 1:
                raise ValidationError(
                    _('El siguiente número de cheque debe ser mayor a cero.')
                )
    
    def check_duplicate_check_number(self, check_number):
        """
        Verificar si un número de cheque ya existe para esta cuenta bancaria.
        
        Args:
            check_number (str): Número de cheque a verificar
            
        Returns:
            dict: Información del cheque duplicado si existe, False si no existe
        """
        self.ensure_one()
        
        # Buscar pagos con este número de cheque en esta cuenta
        existing_check = self.env['l10n_latam.check'].search([
            ('payment_id.journal_id.bank_account_id', '=', self.id),
            ('payment_id.payment_method_code', '=', 'own_checks'),
            ('name', '=', check_number),
            ('check_printed', '=', True)
        ], limit=1)
        
        if existing_check:
            payment = existing_check.payment_id
            return {
                'payment_id': payment.id,
                'payment_name': payment.name,
                'partner_name': payment.partner_id.name,
                'amount': payment.amount,
                'date': payment.payment_date,
                'check_number': check_number
            }
        
        return False
