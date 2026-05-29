# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class L10nEcCheckFormatField(models.Model):
    _name = 'l10n_ec.check.format.field'
    _description = 'Campo de Formato de Cheque'
    _order = 'format_id, sequence, name'

    name = fields.Char(
        string='Nombre Interno',
        required=True,
        help='Identificador interno del campo'
    )
    
    label = fields.Char(
        string='Etiqueta',
        required=True,
        help='Etiqueta visible del campo'
    )
    
    format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de procesamiento del campo'
    )
    
    field_type = fields.Selection([
        ('text', 'Texto'),
        ('number', 'Número'),
        ('date', 'Fecha'),
        ('currency', 'Moneda'),
        ('boolean', 'Verdadero/Falso'),
        ('image', 'Imagen'),
    ], string='Tipo de Campo', required=True, default='text')
    
    # Posicionamiento
    x_position = fields.Float(
        string='Posición X (mm)',
        required=True,
        default=0.0,
        help='Posición horizontal desde el margen izquierdo en milímetros'
    )
    
    y_position = fields.Float(
        string='Posición Y (mm)',
        required=True,
        default=0.0,
        help='Posición vertical desde el margen superior en milímetros'
    )
    
    width = fields.Float(
        string='Ancho (mm)',
        required=True,
        default=50.0,
        help='Ancho del campo en milímetros'
    )
    
    height = fields.Float(
        string='Alto (mm)',
        required=True,
        default=10.0,
        help='Alto del campo en milímetros'
    )
    
    # Formato del texto
    font_family = fields.Selection([
        ('Arial', 'Arial'),
        ('Times New Roman', 'Times New Roman'),
        ('Courier New', 'Courier New'),
        ('Terminal', 'Terminal'),
        ('Helvetica', 'Helvetica'),
        ('Verdana', 'Verdana'),
        ('Miriam Fixed', 'Miriam Fixed'),
        ('Calibri', 'Calibri'),
    ], string='Fuente', default='Arial')
    
    font_size = fields.Integer(
        string='Tamaño de Fuente',
        default=10,
        help='Tamaño de la fuente en puntos'
    )
    
    font_weight = fields.Selection([
        ('normal', 'Normal'),
        ('bold', 'Negrita'),
    ], string='Peso de Fuente', default='normal')
    
    text_align = fields.Selection([
        ('left', 'Izquierda'),
        ('center', 'Centro'),
        ('right', 'Derecha'),
        ('justify', 'Justificado'),
    ], string='Alineación', default='left')
    
    # Validaciones
    is_required = fields.Boolean(
        string='Obligatorio',
        default=False,
        help='Indica si este campo es obligatorio para imprimir'
    )
    
    visible = fields.Boolean(
        string='Visible',
        default=True,
        help='Indica si este campo se muestra en el cheque impreso'
    )
    
    max_length = fields.Integer(
        string='Longitud Máxima',
        help='Número máximo de caracteres permitidos'
    )
    
    # Formato específico para números
    decimal_places = fields.Integer(
        string='Decimales',
        default=2,
        help='Número de decimales para campos numéricos'
    )
    
    show_currency_symbol = fields.Boolean(
        string='Mostrar Símbolo de Moneda',
        default=False,
        help='Mostrar el símbolo de moneda (ej: $) antes del valor'
    )
    
    # Formato específico para fechas
    date_format = fields.Char(
        string='Formato de Fecha',
        default='%d/%m/%Y',
        help='Formato de fecha personalizado usando códigos Python strftime.\n'
             'Ejemplos:\n'
             '  %d/%m/%Y → 15/09/2025\n'
             '  %Y/%m/%d → 2025/09/15\n'
             '  %Y %B %d → 2025 septiembre 15\n'
             '  %Y %b %d → 2025 sep 15\n'
             'Códigos: %d=día, %m=mes, %Y=año, %B=mes completo, %b=mes abreviado'
    )
    
    # Campo de origen de datos
    data_source = fields.Selection([
        ('beneficiary', 'Beneficiario del Cheque'),
        ('partner_id.name', 'Nombre del Beneficiario'),
        ('amount', 'Monto del Pago'),
        ('amount_in_words', 'Monto en Letras'),
        ('payment_date', 'Fecha de Pago'),
        ('date', 'Fecha de Emisión'),
        ('name', 'Número de Cheque'),
        ('communication', 'Referencia/Memo'),
        ('company_id.name', 'Nombre de la Empresa'),
        ('journal_id.name', 'Nombre del Diario'),
        ('journal_id.bank_account_id.acc_number', 'Número de Cuenta'),
        ('currency_id.name', 'Moneda'),
        ('custom', 'Personalizado'),
    ], string='Origen de Datos', required=True)

    custom_value = fields.Char(
        string='Valor Personalizado',
        help='Valor fijo para campos personalizados'
    )
    
    # Configuraciones adicionales
    uppercase = fields.Boolean(
        string='Mayúsculas',
        default=False,
        help='Convertir texto a mayúsculas'
    )
    
    show_border = fields.Boolean(
        string='Mostrar Borde',
        default=False,
        help='Mostrar borde del campo (útil para diseño)'
    )
    
    background_color = fields.Char(
        string='Color de Fondo',
        help='Color de fondo en formato hexadecimal (ej: #FFFFFF)'
    )
    
    text_color = fields.Char(
        string='Color del Texto',
        default='#000000',
        help='Color del texto en formato hexadecimal'
    )
    
    @api.constrains('x_position', 'y_position', 'width', 'height')
    def _check_positive_dimensions(self):
        """Validar que las dimensiones sean positivas"""
        for record in self:
            if record.width <= 0:
                raise ValidationError(_('El ancho debe ser mayor a 0'))
            if record.height <= 0:
                raise ValidationError(_('El alto debe ser mayor a 0'))
            if record.x_position < 0:
                raise ValidationError(_('La posición X no puede ser negativa'))
            if record.y_position < 0:
                raise ValidationError(_('La posición Y no puede ser negativa'))
    
    @api.constrains('font_size')
    def _check_font_size(self):
        """Validar tamaño de fuente"""
        for record in self:
            if record.font_size <= 0:
                raise ValidationError(_('El tamaño de fuente debe ser mayor a 0'))
    
    @api.constrains('max_length')
    def _check_max_length(self):
        """Validar longitud máxima"""
        for record in self:
            if record.max_length and record.max_length <= 0:
                raise ValidationError(_('La longitud máxima debe ser mayor a 0'))
    
    @api.constrains('decimal_places')
    def _check_decimal_places(self):
        """Validar decimales"""
        for record in self:
            if record.decimal_places < 0:
                raise ValidationError(_('El número de decimales no puede ser negativo'))
    
    def name_get(self):
        """Personalizar el nombre mostrado"""
        result = []
        for record in self:
            name = f'{record.label} ({record.name})'
            result.append((record.id, name))
        return result
    
    def action_configure(self):
        """Acción para configurar el campo con el formulario completo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configurar Campo: %s') % self.label,
            'res_model': 'l10n_ec.check.format.field',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_format_id': self.format_id.id,
            }
        }
    
    def _capitalize_month_names(self, date_string, date_format=None):
        """Normalizar nombres de meses a español con inicial mayúscula"""
        # Si el formato usa mes completo, traducir primero nombres completos.
        full_month_map = {
            'enero': 'Enero', 'febrero': 'Febrero', 'marzo': 'Marzo',
            'abril': 'Abril', 'mayo': 'Mayo', 'junio': 'Junio',
            'julio': 'Julio', 'agosto': 'Agosto', 'septiembre': 'Septiembre',
            'octubre': 'Octubre', 'noviembre': 'Noviembre', 'diciembre': 'Diciembre',
            'january': 'Enero', 'february': 'Febrero', 'march': 'Marzo',
            'april': 'Abril', 'may': 'Mayo', 'june': 'Junio', 'july': 'Julio',
            'august': 'Agosto', 'september': 'Septiembre', 'october': 'Octubre',
            'november': 'Noviembre', 'december': 'Diciembre',
        }
        short_month_map = {
            'ene': 'Ene', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Abr',
            'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Ago',
            'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dic',
            'jan': 'Ene', 'apr': 'Abr', 'aug': 'Ago', 'dec': 'Dic',
        }

        result = date_string

        if date_format and '%B' in date_format:
            for source_month, target_month in full_month_map.items():
                pattern = r'\b' + re.escape(source_month) + r'\b'
                result = re.sub(pattern, target_month, result, flags=re.IGNORECASE)

        if date_format and '%b' in date_format:
            for source_month, target_month in short_month_map.items():
                pattern = r'\b' + re.escape(source_month) + r'\b'
                result = re.sub(pattern, target_month, result, flags=re.IGNORECASE)

        return result
    
    def get_field_value(self, check):
        """Obtener el valor del campo para un pago específico"""
        self.ensure_one()
        
        # Manejar campo especial: amount_in_words
        if self.data_source == 'amount_in_words':
            from .amount_to_text import number_to_text_es
            currency_name = check.currency_id.name if check.currency_id else 'DÓLARES'
            value = number_to_text_es(check.amount, currency=currency_name)
        elif self.data_source == 'custom':
            value = self.custom_value or ''
        else:
            # Obtener valor del pago usando la ruta del campo
            try:
                value = check
                for attr in self.data_source.split('.'):
                    value = getattr(value, attr, '') if value else ''
            except (AttributeError, KeyError):
                value = ''
        
        # Aplicar formateo según el tipo de campo
        if self.field_type == 'number' and isinstance(value, (int, float)):
            value = f'{value:.{self.decimal_places}f}'
        elif self.field_type == 'date' and hasattr(value, 'strftime'):
            value = value.strftime(self.date_format)
            # Capitalizar nombres de meses
            value = self._capitalize_month_names(value, self.date_format)
        elif self.field_type == 'currency' and isinstance(value, (int, float)):
            # Solo agregar símbolo si show_currency_symbol está activado
            if self.show_currency_symbol:
                currency_symbol = check.currency_id.symbol if check.currency_id else '$'
                value = f'{currency_symbol} {value:.{self.decimal_places}f}'
            else:
                value = f'{value:.{self.decimal_places}f}'
        elif self.field_type == 'boolean':
            value = 'Sí' if value else 'No'
        
        # Convertir a string y aplicar transformaciones
        value = str(value) if value else ''
        
        if self.uppercase:
            value = value.upper()
        
        if self.max_length and len(value) > self.max_length:
            value = value[:self.max_length]
        
        return value
