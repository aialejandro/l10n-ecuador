# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    # Campo computado para el formato de cheque
    l10n_ec_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque',
        compute='_compute_l10n_ec_check_format_id',
        store=True,
        help='Formato de cheque que se usará para imprimir este pago'
    )
    
    # Campo para verificar si puede imprimir cheque
    can_print_check = fields.Boolean(
        string='Puede Imprimir Cheque',
        compute='_compute_can_print_check'
    )
    
    @api.depends('journal_id', 'journal_id.l10n_ec_check_format_id', 
                 'journal_id.bank_id', 'journal_id.bank_id.default_check_format_id')
    def _compute_l10n_ec_check_format_id(self):
        """Obtener el formato de cheque basado en el diario"""
        for payment in self:
            if payment.journal_id:
                payment.l10n_ec_check_format_id = payment.journal_id.get_check_format()
            else:
                payment.l10n_ec_check_format_id = False
    
    @api.depends('payment_method_code', 'l10n_ec_check_format_id')
    def _compute_can_print_check(self):
        """Determinar si se puede imprimir el cheque"""
        for payment in self:
            payment.can_print_check = (
                payment.payment_method_code == 'check_printing' and
                bool(payment.l10n_ec_check_format_id)
            )
    
    def action_print_checks(self):
        """Acción para imprimir cheques con formato ecuatoriano"""
        if not self:
            return
        
        # Verificar que todos los pagos tengan formato
        payments_without_format = self.filtered(lambda p: not p.l10n_ec_check_format_id)
        if payments_without_format:
            raise UserError(_(
                'Los siguientes pagos no tienen formato de cheque configurado:\n%s\n\n'
                'Configure un formato de cheque para el banco en el diario correspondiente.'
            ) % '\n'.join(payments_without_format.mapped('name')))
        
        # Verificar que todos tengan el mismo formato
        formats = self.mapped('l10n_ec_check_format_id')
        if len(formats) > 1:
            raise UserError(_(
                'No se pueden imprimir cheques con formatos diferentes en una sola operación. '
                'Seleccione pagos que usen el mismo formato.'
            ))
        
        # Verificar campos obligatorios
        for payment in self:
            missing_fields = []
            format_fields = payment.l10n_ec_check_format_id.format_field_ids.filtered('is_required')
            
            for field in format_fields:
                value = field.get_field_value(payment)
                if not value:
                    missing_fields.append(field.label)
            
            if missing_fields:
                raise UserError(_(
                    'El pago %s tiene campos obligatorios sin completar:\n%s'
                ) % (payment.name, '\n'.join(missing_fields)))
        
        # Generar reporte (temporalmente deshabilitado)
        # TODO: Crear reporte de impresión de cheques
        # return self.env.ref('l10n_ec_check.action_report_check_print').report_action(self)
        
        # Por ahora, mostramos un mensaje informativo
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Impresión de Cheques'),
                'message': _('Función de impresión será implementada en la siguiente fase. Formato configurado: %s') % self[0].l10n_ec_check_format_id.name,
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_preview_check(self):
        """Acción para previsualizar el cheque"""
        self.ensure_one()
        
        if not self.l10n_ec_check_format_id:
            raise UserError(_(
                'No hay formato de cheque configurado para este pago. '
                'Configure un formato para el banco en el diario correspondiente.'
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista Previa: %s') % self.name,
            'res_model': 'l10n_ec.check.format.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_format_id': self.l10n_ec_check_format_id.id,
                'default_payment_id': self.id,
                'default_preview_mode': True,
            }
        }
