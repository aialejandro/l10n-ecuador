# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class L10nEcCheckFormat(models.Model):
    _name = 'l10n_ec.check.format'
    _description = 'Formato de Cheque Ecuatoriano'
    _order = 'bank_id, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre del Formato',
        required=True,
        help='Nombre descriptivo del formato de cheque'
    )
    
    bank_id = fields.Many2one(
        'res.bank',
        string='Banco',
        required=True,
        help='Banco al que pertenece este formato'
    )
    
    is_default = fields.Boolean(
        string='Formato por Defecto',
        default=False,
        help='Indica si este es el formato por defecto para el banco'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción detallada del formato'
    )
    
    # Configuración del papel
    paper_size = fields.Selection([
        ('letter', 'Carta (8.5" x 11")'),
        ('legal', 'Legal (8.5" x 14")'),
        ('a4', 'A4 (210mm x 297mm)'),
        ('custom', 'Personalizado')
    ], string='Tamaño del Papel', default='letter', required=True)
    
    orientation = fields.Selection([
        ('portrait', 'Vertical'),
        ('landscape', 'Horizontal')
    ], string='Orientación', default='landscape', required=True)
    
    # Dimensiones personalizadas (en milímetros)
    paper_width = fields.Float(
        string='Ancho del Papel (mm)',
        help='Ancho del papel en milímetros (solo para tamaño personalizado)'
    )
    paper_height = fields.Float(
        string='Alto del Papel (mm)',
        help='Alto del papel en milímetros (solo para tamaño personalizado)'
    )
    
    # Márgenes en milímetros
    margin_top = fields.Float(
        string='Margen Superior (mm)',
        default=10.0
    )
    margin_bottom = fields.Float(
        string='Margen Inferior (mm)',
        default=10.0
    )
    margin_left = fields.Float(
        string='Margen Izquierdo (mm)',
        default=10.0
    )
    margin_right = fields.Float(
        string='Margen Derecho (mm)',
        default=10.0
    )
    
    # Relación con campos del formato
    format_field_ids = fields.One2many(
        'l10n_ec.check.format.field',
        'format_id',
        string='Campos del Formato'
    )
    
    # Campos computados
    field_count = fields.Integer(
        string='Número de Campos',
        compute='_compute_field_count'
    )
    
    journal_ids = fields.One2many(
        'account.journal',
        'l10n_ec_check_format_id',
        string='Diarios que usan este formato',
        readonly=True
    )
    
    @api.depends('format_field_ids')
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.format_field_ids)
    
    @api.constrains('is_default', 'bank_id', 'active')
    def _check_unique_default_per_bank(self):
        """Asegurar que solo hay un formato por defecto activo por banco"""
        for record in self:
            if record.is_default and record.active:
                existing = self.search([
                    ('bank_id', '=', record.bank_id.id),
                    ('is_default', '=', True),
                    ('active', '=', True),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_(
                        'Solo puede haber un formato por defecto activo por banco. '
                        'El banco %s ya tiene un formato por defecto: %s'
                    ) % (record.bank_id.name, existing[0].name))
    
    @api.constrains('paper_width', 'paper_height', 'paper_size')
    def _check_custom_paper_dimensions(self):
        """Validar dimensiones personalizadas del papel"""
        for record in self:
            if record.paper_size == 'custom':
                if not record.paper_width or record.paper_width <= 0:
                    raise ValidationError(_('El ancho del papel debe ser mayor a 0 para tamaño personalizado'))
                if not record.paper_height or record.paper_height <= 0:
                    raise ValidationError(_('El alto del papel debe ser mayor a 0 para tamaño personalizado'))
    
    def name_get(self):
        """Personalizar el nombre mostrado"""
        result = []
        for record in self:
            name = record.name
            if record.bank_id:
                name = f'{record.bank_id.name} - {name}'
            if record.is_default:
                name += _(' (Por Defecto)')
            result.append((record.id, name))
        return result
    
    def get_paper_dimensions(self):
        """Obtener las dimensiones del papel en milímetros"""
        self.ensure_one()
        
        if self.paper_size == 'custom':
            return (self.paper_width, self.paper_height)
        
        # Dimensiones estándar en milímetros
        dimensions = {
            'letter': (215.9, 279.4),
            'legal': (215.9, 355.6),
            'a4': (210, 297),
        }
        
        width, height = dimensions.get(self.paper_size, (215.9, 279.4))
        
        # Intercambiar si es horizontal
        if self.orientation == 'landscape':
            width, height = height, width
            
        return (width, height)
    
    def create_default_fields(self):
        """Crear campos por defecto para un nuevo formato"""
        self.ensure_one()
        
        default_fields = [
            {
                'name': 'beneficiary',
                'label': 'Beneficiario',
                'field_type': 'text',
                'x_position': 50,
                'y_position': 100,
                'width': 200,
                'height': 20,
                'font_size': 12,
                'is_required': True,
            },
            {
                'name': 'amount_words',
                'label': 'Monto en Letras',
                'field_type': 'text',
                'x_position': 50,
                'y_position': 70,
                'width': 300,
                'height': 20,
                'font_size': 11,
                'is_required': True,
            },
            {
                'name': 'amount_numbers',
                'label': 'Monto en Números',
                'field_type': 'number',
                'x_position': 400,
                'y_position': 100,
                'width': 100,
                'height': 20,
                'font_size': 12,
                'is_required': True,
            },
            {
                'name': 'payment_date',
                'label': 'Fecha',
                'field_type': 'date',
                'x_position': 400,
                'y_position': 140,
                'width': 80,
                'height': 20,
                'font_size': 10,
                'is_required': True,
            },
            {
                'name': 'check_number',
                'label': 'Número de Cheque',
                'field_type': 'text',
                'x_position': 450,
                'y_position': 200,
                'width': 80,
                'height': 15,
                'font_size': 10,
                'is_required': False,
            },
        ]
        
        for field_data in default_fields:
            field_data['format_id'] = self.id
            self.env['l10n_ec.check.format.field'].create(field_data)
    
    def action_preview_format(self):
        """Acción para previsualizar el formato"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista Previa: %s') % self.name,
            'res_model': 'l10n_ec.check.format.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_format_id': self.id,
                'default_preview_mode': True,
            }
        }
    
    def action_edit_visual(self):
        """Acción para abrir el editor visual - versión temporal"""
        self.ensure_one()
        
        # Por ahora, abrimos el formulario de campos relacionados
        # TODO: Implementar editor visual drag-and-drop
        return {
            'type': 'ir.actions.act_window',
            'name': _('Editar Campos del Formato: %s') % self.name,
            'res_model': 'l10n_ec.check.format.field',
            'view_mode': 'tree,form',
            'domain': [('format_id', '=', self.id)],
            'context': {
                'default_format_id': self.id,
                'search_default_format_id': self.id,
            },
            'target': 'current',
        }
