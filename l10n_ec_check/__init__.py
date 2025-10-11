# -*- coding: utf-8 -*-

from . import models
from . import wizards

# Función comentada temporalmente
# def _post_init_hook(cr, registry):
#     """Post-install hook to setup default data"""
#     from odoo import api, SUPERUSER_ID
    
#     env = api.Environment(cr, SUPERUSER_ID, {})
    
#     # Crear formatos de cheque por defecto para bancos ecuatorianos más comunes
#     banks_to_setup = [
#         'Banco del Pacífico',
#         'Banco Pichincha',
#         'Banco de Guayaquil',
#         'Banco Internacional',
#         'Produbanco',
#     ]
    
#     for bank_name in banks_to_setup:
#         bank = env['res.bank'].search([('name', 'ilike', bank_name)], limit=1)
#         if bank:
#             # Crear formato básico si no existe
#             existing_format = env['l10n_ec.check.format'].search([
#                 ('bank_id', '=', bank.id),
#                 ('is_default', '=', True)
#             ], limit=1)
            
#             if not existing_format:
#                 env['l10n_ec.check.format'].create({
#                     'name': f'Formato Estándar {bank.name}',
#                     'bank_id': bank.id,
#                     'is_default': True,
#                     'paper_size': 'letter',
#                     'orientation': 'landscape',
#                     'description': f'Formato por defecto para {bank.name}',
#                 })
