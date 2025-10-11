# -*- coding: utf-8 -*-

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
        ('Helvetica', 'Helvetica'),
        ('Verdana', 'Verdana'),
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
    
    # Formato específico para fechas
    date_format = fields.Selection([
        ('%d/%m/%Y', 'DD/MM/AAAA'),
        ('%m/%d/%Y', 'MM/DD/AAAA'),
        ('%Y-%m-%d', 'AAAA-MM-DD'),
        ('%d de %B de %Y', 'DD de Mes de AAAA'),
    ], string='Formato de Fecha', default='%d/%m/%Y')
    
    # Campo de origen de datos
    data_source = fields.Selection([
        ('payment.partner_id.name', 'Nombre del Beneficiario'),
        ('payment.amount', 'Monto del Pago'),
        ('payment.date', 'Fecha del Pago'),
        ('payment.check_number', 'Número de Cheque'),
        ('payment.communication', 'Referencia/Memo'),
        ('payment.company_id.name', 'Nombre de la Empresa'),
        ('payment.journal_id.name', 'Nombre del Diario'),
        ('payment.journal_id.bank_account_id.acc_number', 'Número de Cuenta'),
        ('payment.currency_id.name', 'Moneda'),
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
    
    def get_field_value(self, payment):
        """Obtener el valor del campo para un pago específico"""
        self.ensure_one()
        
        if self.data_source == 'custom':
            value = self.custom_value or ''
        else:
            # Obtener valor del pago usando la ruta del campo
            try:
                value = payment
                for attr in self.data_source.split('.')[1:]:  # Saltar 'payment'
                    value = getattr(value, attr, '') if value else ''
            except (AttributeError, KeyError):
                value = ''
        
        # Aplicar formateo según el tipo de campo
        if self.field_type == 'number' and isinstance(value, (int, float)):
            value = f'{value:.{self.decimal_places}f}'
        elif self.field_type == 'date' and hasattr(value, 'strftime'):
            value = value.strftime(self.date_format)
        elif self.field_type == 'currency' and isinstance(value, (int, float)):
            currency_symbol = payment.currency_id.symbol if payment.currency_id else '$'
            value = f'{currency_symbol} {value:.{self.decimal_places}f}'
        elif self.field_type == 'boolean':
            value = 'Sí' if value else 'No'
        
        # Convertir a string y aplicar transformaciones
        value = str(value) if value else ''
        
        if self.uppercase:
            value = value.upper()
        
        if self.max_length and len(value) > self.max_length:
            value = value[:self.max_length]
        
        return value
