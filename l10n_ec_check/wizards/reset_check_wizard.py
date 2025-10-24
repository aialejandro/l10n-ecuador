# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from passlib.context import CryptContext


class L10nEcCheckResetWizard(models.TransientModel):
    _name = 'l10n_ec.check.reset.wizard'
    _description = 'Wizard para Resetear Impresión de Cheques'

    payment_ids = fields.Many2many(
        'account.payment',
        string='Pagos a Resetear',
        required=True,
        readonly=True
    )
    
    password = fields.Char(
        string='Contraseña de Administrador',
        help='Ingrese la contraseña del usuario actual para confirmar el reseteo'
    )
    
    payment_count = fields.Integer(
        string='Cantidad de Pagos',
        compute='_compute_payment_count'
    )
    
    payment_details = fields.Html(
        string='Detalles de Pagos',
        compute='_compute_payment_details'
    )
    
    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for wizard in self:
            wizard.payment_count = len(wizard.payment_ids)
    
    @api.depends('payment_ids')
    def _compute_payment_details(self):
        for wizard in self:
            if not wizard.payment_ids:
                wizard.payment_details = '<p>No hay pagos seleccionados</p>'
                continue
            
            html = '<table class="table table-sm table-striped">'
            html += '<thead><tr>'
            html += '<th>Pago</th>'
            html += '<th>Número de Cheque</th>'
            html += '<th>Monto</th>'
            html += '<th>Impreso el</th>'
            html += '<th>Impreso por</th>'
            html += '</tr></thead><tbody>'
            
            for payment in wizard.payment_ids:
                html += '<tr>'
                html += f'<td>{payment.name}</td>'
                html += f'<td><strong>{payment.l10n_ec_check_number or "N/A"}</strong></td>'
                html += f'<td>{payment.currency_id.symbol} {payment.amount:,.2f}</td>'
                html += f'<td>{payment.check_print_date.strftime("%Y-%m-%d %H:%M") if payment.check_print_date else "N/A"}</td>'
                html += f'<td>{payment.check_printed_by.name if payment.check_printed_by else "Desconocido"}</td>'
                html += '</tr>'
            
            html += '</tbody></table>'
            wizard.payment_details = html
    
    def action_confirm_reset(self):
        """
        Validar la contraseña y ejecutar el reseteo.
        """
        self.ensure_one()
        
        # Validar que haya contraseña
        if not self.password:
            raise ValidationError(_('Debe ingresar su contraseña para continuar.'))
        
        # Obtener el usuario actual
        current_user = self.env.user
        
        # Intentar autenticar con la contraseña
        try:
            # Validar usando sudo() con nueva conexión
            uid = self.env['res.users'].sudo().with_context(no_reset_password=True).search([
                ('id', '=', current_user.id),
                ('login', '=', current_user.login)
            ], limit=1)
            
            if not uid:
                raise ValidationError(_('Usuario no encontrado.'))
            
            # Verificar la contraseña directamente con la BD
            self.env.cr.execute(
                "SELECT password FROM res_users WHERE id = %s",
                (current_user.id,)
            )
            result = self.env.cr.fetchone()
            stored_password = result[0] if result else None
            
            # Si hay contraseña guardada en BD, validar con passlib
            if stored_password:
                crypt_context = CryptContext(
                    schemes=['pbkdf2_sha512', 'plaintext'],
                    deprecated=['plaintext']
                )
                valid = crypt_context.verify(self.password, stored_password)
                if not valid:
                    raise ValidationError(_('Contraseña incorrecta.'))
            else:
                # Si no hay contraseña en BD, intentar con authenticate del http
                # (útil para usuarios con autenticación externa)
                from odoo.http import db_monodb
                try:
                    authenticated_uid = self.env['res.users']._authenticate(
                        self.env.cr.dbname,
                        current_user.login,
                        self.password
                    )
                    if authenticated_uid != current_user.id:
                        raise ValidationError(_('Contraseña incorrecta.'))
                except Exception:
                    raise ValidationError(_(
                        'No se pudo validar la contraseña. '
                        'El usuario puede no tener contraseña configurada.'
                    ))
                    
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_(
                'Error al validar la contraseña: %s'
            ) % str(e))
        
        # Si la validación es exitosa, ejecutar el reseteo
        self.payment_ids.confirm_reset_check_printed()
        
        # Retornar acción para recargar la vista
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _(
                    'Se ha reseteado el estado de impresión de %d pago(s). '
                    'Los cheques pueden ser reimpresos.'
                ) % len(self.payment_ids),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }
    
    def action_cancel(self):
        """
        Cancelar el wizard sin hacer cambios.
        """
        return {'type': 'ir.actions.act_window_close'}
