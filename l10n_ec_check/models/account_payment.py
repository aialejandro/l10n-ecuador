# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    # Campo computado para el formato de cheque
    l10n_ec_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque',
        compute='_compute_l10n_ec_check_format_id',
        store=True,
        readonly=False,
        help='Formato de cheque que se usará para imprimir este pago'
    )
    
    # Campo para verificar si puede imprimir cheque
    can_print_check = fields.Boolean(
        string='Puede Imprimir Cheque',
        compute='_compute_can_print_check'
    )
    
    # Control de impresión de cheques
    check_printed = fields.Boolean(
        string='Cheque Impreso',
        default=False,
        copy=False,
        help='Indica si el cheque ya fue impreso. Para reimprimir, debe cambiar este campo a False desde la base de datos.'
    )
    
    check_print_date = fields.Datetime(
        string='Fecha de Impresión',
        readonly=True,
        copy=False,
        help='Fecha y hora en que se imprimió el cheque'
    )
    
    check_printed_by = fields.Many2one(
        'res.users',
        string='Impreso por',
        readonly=True,
        copy=False,
        help='Usuario que imprimió el cheque'
    )
    
    # Número de cheque
    l10n_ec_check_number = fields.Char(
        string='Número de Cheque',
        readonly=True,
        copy=False,
        help='Número del cheque impreso'
    )
    
    @api.depends('journal_id', 'journal_id.l10n_ec_check_format_id',
                 'journal_id.bank_account_id', 'journal_id.bank_account_id.l10n_ec_check_format_id',
                 'journal_id.bank_id', 'journal_id.bank_id.default_check_format_id',
                 'payment_method_code')
    def _compute_l10n_ec_check_format_id(self):
        """Obtener el formato de cheque basado en el diario"""
        for payment in self:
            # Solo calcular si es pago por cheque
            if payment.payment_method_code == 'check_printing' and payment.journal_id:
                check_format = payment.journal_id.get_check_format()
                if check_format:
                    payment.l10n_ec_check_format_id = check_format
                else:
                    payment.l10n_ec_check_format_id = False
            else:
                payment.l10n_ec_check_format_id = False
    
    @api.depends('payment_method_code', 'l10n_ec_check_format_id', 'check_printed')
    def _compute_can_print_check(self):
        """Determinar si se puede imprimir el cheque"""
        for payment in self:
            payment.can_print_check = (
                payment.payment_method_code == 'check_printing' and
                bool(payment.l10n_ec_check_format_id) and
                not payment.check_printed
            )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para asegurar que se asigne formato de cheque"""
        payments = super().create(vals_list)
        # Forzar recálculo del formato para pagos con cheque
        check_payments = payments.filtered(lambda p: p.payment_method_code == 'check_printing')
        if check_payments:
            check_payments._compute_l10n_ec_check_format_id()
        return payments
    
    def write(self, vals):
        """Override write para recalcular formato si cambia el diario o método de pago"""
        result = super().write(vals)
        # Si cambió el diario o el método de pago, recalcular formato
        if 'journal_id' in vals or 'payment_method_code' in vals or 'payment_method_line_id' in vals:
            check_payments = self.filtered(lambda p: p.payment_method_code == 'check_printing')
            if check_payments:
                check_payments._compute_l10n_ec_check_format_id()
        return result
    
    def action_print_checks(self):
        """Acción para imprimir cheques con formato ecuatoriano"""
        if not self:
            return
        
        # Verificar que no hayan cheques ya impresos
        already_printed = self.filtered('check_printed')
        if already_printed:
            raise UserError(_(
                'Los siguientes pagos ya tienen cheques impresos:\n%s\n\n'
                'Para reimprimir, use el botón "Resetear Impresión" (requiere permisos de administrador).'
            ) % '\n'.join(already_printed.mapped('name')))
        
        # Intentar recalcular el formato si no está asignado
        payments_without_format = self.filtered(lambda p: not p.l10n_ec_check_format_id)
        if payments_without_format:
            # Intentar obtener el formato del diario
            for payment in payments_without_format:
                if payment.journal_id:
                    check_format = payment.journal_id.get_check_format()
                    if check_format:
                        payment.l10n_ec_check_format_id = check_format
            
            # Verificar de nuevo después de intentar asignar
            still_without_format = self.filtered(lambda p: not p.l10n_ec_check_format_id)
            if still_without_format:
                # Intentar usar formato genérico como último recurso
                generic_format = self.env.ref('l10n_ec_check.l10n_ec_check_format_generic', raise_if_not_found=False)
                if generic_format and generic_format.active:
                    for payment in still_without_format:
                        payment.l10n_ec_check_format_id = generic_format
                else:
                    raise UserError(_(
                        'Los siguientes pagos no tienen formato de cheque configurado:\n%s\n\n'
                        'SOLUCIÓN:\n'
                        '1. Vaya a: Facturación → Configuración → Diarios\n'
                        '2. Abra el diario: %s\n'
                        '3. Asigne un formato de cheque en la pestaña principal\n\n'
                        'Si no existen formatos, créelos en:\n'
                        '   Facturación → Configuración → Formatos de Cheque'
                    ) % ('\n'.join(still_without_format.mapped('name')), 
                         still_without_format[0].journal_id.name if still_without_format else 'N/A'))
        
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
        
        # Asignar números de cheque antes de imprimir
        self._assign_check_numbers()
        
        # Marcar como impreso antes de generar el reporte
        self.write({
            'check_printed': True,
            'check_print_date': fields.Datetime.now(),
            'check_printed_by': self.env.user.id,
        })
        
        # Generar el reporte de impresión de cheques
        return self.env.ref('l10n_ec_check.action_report_check_print').report_action(self)
    
    def action_preview_check(self):
        """Acción para previsualizar el cheque"""
        self.ensure_one()
        
        if not self.l10n_ec_check_format_id:
            raise UserError(_(
                'No hay formato de cheque configurado para este pago.\n\n'
                'Para configurar un formato de cheque, vaya a:\n'
                '  Contabilidad → Configuración → Formatos de Cheque\n'
                'O bien:\n'
                '  Cheques Ecuador → Configuración → Formatos de Cheque\n\n'
                'Luego asigne el formato al diario bancario "%s".'
            ) % self.journal_id.name)
        
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
    
    def action_reset_check_printed(self):
        """
        Abrir wizard para resetear el estado de impresión del cheque.
        Requiere confirmación con contraseña del usuario actual.
        """
        # Verificar permisos de administrador
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Solo los administradores del sistema pueden resetear el estado de impresión de cheques.'
            ))
        
        already_printed = self.filtered('check_printed')
        if not already_printed:
            raise UserError(_('Los pagos seleccionados no tienen cheques impresos.'))
        
        # Abrir wizard de confirmación con contraseña
        return {
            'name': _('Confirmar Reseteo de Impresión'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_ec.check.reset.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_ids': [(6, 0, already_printed.ids)],
            }
        }
    
    def confirm_reset_check_printed(self):
        """
        Método interno para confirmar el reseteo después de validar la contraseña.
        Llamado desde el wizard.
        """
        already_printed = self.filtered('check_printed')
        
        # Registrar la acción en el chatter con detalles completos
        for payment in already_printed:
            payment.message_post(
                body=_(
                    '⚠️ RESETEO DE IMPRESIÓN DE CHEQUE\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                    'Reseteado por: %s\n'
                    'Fecha de reseteo: %s\n'
                    'Número de cheque: %s\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                    'Datos del cheque original:\n'
                    '  • Impreso el: %s\n'
                    '  • Impreso por: %s\n'
                    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                    '⚠️ El cheque puede ser reimpreso'
                ) % (
                    self.env.user.name,
                    fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    payment.l10n_ec_check_number or 'N/A',
                    payment.check_print_date.strftime('%Y-%m-%d %H:%M:%S') if payment.check_print_date else 'N/A',
                    payment.check_printed_by.name if payment.check_printed_by else _('Usuario desconocido')
                ),
                subject=_('🔓 Reseteo de Estado de Impresión de Cheque'),
                message_type='notification',
            )
        
        # Resetear campos (mantener el número de cheque asignado)
        already_printed.write({
            'check_printed': False,
            'check_print_date': False,
            'check_printed_by': False,
            # NO resetear l10n_ec_check_number - mantener el número original
        })
        
        return True
    
    def _assign_check_numbers(self):
        """Asignar números de cheque consecutivos a los pagos"""
        for payment in self:
            if not payment.l10n_ec_check_number:
                # Obtener la cuenta bancaria del diario
                bank_account = payment.journal_id.bank_account_id
                
                if bank_account:
                    # Buscar un número disponible (sin duplicados)
                    check_number_int = bank_account.l10n_ec_check_next_number
                    max_attempts = 1000  # Protección contra bucle infinito
                    attempts = 0
                    
                    while attempts < max_attempts:
                        check_number = str(check_number_int).zfill(8)
                        
                        # Verificar si este número ya existe
                        duplicate_info = bank_account.check_duplicate_check_number(check_number)
                        
                        if not duplicate_info:
                            # Número disponible, asignar
                            payment.l10n_ec_check_number = check_number
                            
                            # Actualizar el contador al siguiente número
                            bank_account.sudo().write({
                                'l10n_ec_check_next_number': check_number_int + 1
                            })
                            break
                        else:
                            # Número duplicado, intentar con el siguiente
                            check_number_int += 1
                            attempts += 1
                    
                    if attempts >= max_attempts:
                        raise ValidationError(
                            _('No se pudo encontrar un número de cheque disponible después de %s intentos. '
                              'Por favor, ajuste manualmente el "Siguiente Número de Cheque" en la cuenta bancaria.') % max_attempts
                        )
                else:
                    # Si no hay cuenta bancaria, usar secuencia simple
                    check_number = str(self.env['ir.sequence'].next_by_code('l10n_ec.check.number') or '00000001')
                    payment.l10n_ec_check_number = check_number

