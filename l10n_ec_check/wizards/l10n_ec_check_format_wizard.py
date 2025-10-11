# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class L10nEcCheckFormatWizard(models.TransientModel):
    _name = 'l10n_ec.check.format.wizard'
    _description = 'Wizard de Vista Previa de Formato de Cheque'

    format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque',
        required=True
    )
    
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago (para vista previa)',
        help='Pago de ejemplo para mostrar datos reales en la vista previa'
    )
    
    preview_mode = fields.Boolean(
        string='Modo Vista Previa',
        default=True
    )
    
    # Campos del formato para vista previa
    format_field_ids = fields.One2many(
        related='format_id.format_field_ids',
        readonly=True
    )
    
    # Información del papel
    paper_info = fields.Char(
        string='Información del Papel',
        compute='_compute_paper_info'
    )
    
    # Vista previa HTML
    preview_html = fields.Html(
        string='Vista Previa',
        compute='_compute_preview_html'
    )
    
    @api.depends('format_id')
    def _compute_paper_info(self):
        for record in self:
            if record.format_id:
                width, height = record.format_id.get_paper_dimensions()
                record.paper_info = f'{record.format_id.paper_size.upper()} - {record.format_id.orientation.title()} ({width:.1f}mm x {height:.1f}mm)'
            else:
                record.paper_info = ''
    
    @api.depends('format_id', 'payment_id', 'format_field_ids')
    def _compute_preview_html(self):
        for record in self:
            if not record.format_id:
                record.preview_html = '<p>No hay formato seleccionado</p>'
                continue
            
            # Crear HTML de vista previa
            width, height = record.format_id.get_paper_dimensions()
            html = '''
            <div style="position: relative; border: 2px solid #ccc; margin: 20px; background: white; max-width: 800px;">
                <div style="background: #f0f0f0; padding: 10px; border-bottom: 1px solid #ccc;">
                    <strong>Vista Previa: ''' + str(record.format_id.name) + '''</strong><br/>
                    <small>''' + str(record.paper_info) + '''</small>
                </div>
                <div style="position: relative; min-height: 400px; padding: 20px; background-color: #fafafa; border: 1px dashed #ccc;">
            '''
            
            # Agregar campos
            if record.format_field_ids:
                for field in record.format_field_ids:
                    value = 'Valor de ejemplo'
                    if record.payment_id:
                        value = field.get_field_value(record.payment_id) or 'Sin valor'
                    elif field.custom_value:
                        value = field.custom_value
                    elif field.data_source == 'payment.partner_id.name':
                        value = 'ACME Corporation S.A.'
                    elif field.data_source == 'payment.amount':
                        if field.field_type == 'currency':
                            value = '$ 1,250.50'
                        else:
                            value = 'MIL DOSCIENTOS CINCUENTA CON 50/100'
                    elif field.data_source == 'payment.date':
                        value = '15/08/2025'
                    elif field.data_source == 'payment.check_number':
                        value = '001234'
                    
                    # Crear div para cada campo
                    field_style = []
                    field_style.append('position: absolute')
                    field_style.append('left: ' + str(field.x_position) + 'px')
                    field_style.append('top: ' + str(field.y_position) + 'px')
                    field_style.append('width: ' + str(field.width) + 'px')
                    field_style.append('height: ' + str(field.height) + 'px')
                    field_style.append('font-family: ' + (field.font_family or 'Arial') + ', sans-serif')
                    field_style.append('font-size: ' + str(field.font_size) + 'px')
                    field_style.append('font-weight: ' + str(field.font_weight))
                    field_style.append('text-align: ' + str(field.text_align))
                    field_style.append('color: ' + str(field.text_color or '#000000'))
                    field_style.append('border: ' + ('1px solid #ccc' if field.show_border else 'none'))
                    field_style.append('background: ' + str(field.background_color or 'transparent'))
                    field_style.append('padding: 2px')
                    field_style.append('overflow: hidden')
                    field_style.append('line-height: 1.2')
                    field_style.append('z-index: 10')
                    field_style.append('box-sizing: border-box')
                    
                    style = '; '.join(field_style)
                    
                    html += '<div style="' + style + '" title="' + str(field.label) + ' (' + str(field.name) + ')">'
                    html += '<span style="white-space: nowrap; display: block; overflow: hidden; text-overflow: ellipsis;">' + str(value) + '</span>'
                    html += '</div>'
            else:
                html += '<p style="text-align: center; color: #999; margin-top: 150px;">No hay campos configurados en este formato</p>'
            
            html += '''
                </div>
                <div style="background: #f0f0f0; padding: 10px; border-top: 1px solid #ccc; font-size: 12px; color: #666;">
                    <strong>Nota:</strong> Esta es una vista previa aproximada. La posición real puede variar según la impresora.
                </div>
            </div>
            '''
            
            record.preview_html = html
    
    def action_close(self):
        """Cerrar el wizard"""
        return {'type': 'ir.actions.act_window_close'}
    
    def action_edit_format(self):
        """Ir a editar el formato"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Editar Formato'),
            'res_model': 'l10n_ec.check.format',
            'res_id': self.format_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
