# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResBank(models.Model):
    _inherit = 'res.bank'
    
    # Relación con formatos de cheque
    check_format_ids = fields.One2many(
        'l10n_ec.check.format',
        'bank_id',
        string='Formatos de Cheque'
    )
    
    default_check_format_id = fields.Many2one(
        'l10n_ec.check.format',
        string='Formato de Cheque por Defecto',
        domain="[('bank_id', '=', id), ('active', '=', True)]",
        compute='_compute_default_check_format_id',
        store=True
    )
    
    check_format_count = fields.Integer(
        string='Cantidad de Formatos',
        compute='_compute_check_format_count'
    )
    
    @api.depends('check_format_ids', 'check_format_ids.is_default', 'check_format_ids.active')
    def _compute_default_check_format_id(self):
        """Obtener el formato por defecto activo"""
        for record in self:
            default_format = record.check_format_ids.filtered(
                lambda f: f.is_default and f.active
            )
            record.default_check_format_id = default_format[0] if default_format else False
    
    @api.depends('check_format_ids')
    def _compute_check_format_count(self):
        """Contar formatos de cheque"""
        for record in self:
            record.check_format_count = len(record.check_format_ids)
    
    def action_view_check_formats(self):
        """Acción para ver los formatos de cheque del banco"""
        self.ensure_one()
        action = self.env.ref('l10n_ec_check.action_l10n_ec_check_format').read()[0]
        action['domain'] = [('bank_id', '=', self.id)]
        action['context'] = {'default_bank_id': self.id}
        return action
