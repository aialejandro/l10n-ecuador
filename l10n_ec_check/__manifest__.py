# -*- coding: utf-8 -*-
{
    'name': 'Ecuador - Gestión e Impresión de Cheques por Formato Bancario',
    'version': '18.0.1.15.0',
    'category': 'Accounting/Localizations',
    'summary': 'Gestión de cheques con numeración automática, control de duplicados y tracking completo - Ecuador',
    'description': """
Gestión e Impresión de Cheques por Formato Bancario - Ecuador
==============================================================

Este módulo extiende la funcionalidad de l10n_latam_check para Ecuador con las siguientes características:

Gestión de Formatos de Cheque
------------------------------

* Crear nuevos formatos de cheque con campos posicionables
* Modificar formatos existentes mediante una interfaz visual
* Eliminar o desactivar formatos obsoletos

Asociación por Banco
--------------------

* Asignar uno o varios formatos de cheque a cada banco registrado en Odoo
* Establecer un formato predeterminado por banco (único activo por banco)

Impresión de Cheques
--------------------

* El sistema selecciona automáticamente el formato asignado al banco del diario contable
* Previsualización antes de imprimir
* Compatibilidad con impresoras estándar y configuración de márgenes

Interfaz de Usuario
-------------------

* Editor visual tipo "drag-and-drop" para posicionar campos como:

  - Monto en letras
  - Monto en números
  - Beneficiario
  - Fecha
  - Firma
  - Código de sucursal
  - Número de cuenta

* Validación de campos obligatorios antes de guardar el formato

Características Especiales
---------------------------

* Soporte para múltiples tamaños de papel y orientación
* Definir fuentes, tamaños y alineaciones para cada campo
* Manejo de excepciones como cheques anulados o reimpresiones
* Exportar/importar formatos para reutilización
    """,
    'author': 'ILS - Ivan L. Sistemas',
    'website': 'https://www.ils.ec',
    'license': 'LGPL-3',
    'depends': [
        'l10n_latam_check',
        'l10n_ec',  # Módulo base de Ecuador (si existe)
        'web',
    ],
    'data': [
        # Security
        'security/l10n_ec_check_groups.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/l10n_ec_check_data.xml',
        
        # Views - orden importante: primero los campos, luego los formatos que los referencian
        'views/l10n_ec_check_format_field_views.xml',
        'views/l10n_ec_check_format_views.xml',
        'views/res_bank_views.xml',
        'views/res_partner_bank_views.xml',
        'views/account_journal_views.xml',
        'views/account_payment_views.xml',
        'views/l10n_ec_check_menus.xml',
        
        # Reports
        'report/l10n_ec_check_report.xml',
        'report/report_payment_receipt_templates.xml',
        
        # Wizards
        'wizards/l10n_ec_check_format_wizard_views.xml',
        'wizards/reset_check_wizard_views.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'l10n_ec_check/static/src/js/**/*',
    #         'l10n_ec_check/static/src/css/**/*',
    #     ],
    # },
    # 'demo': [
    #     'demo/l10n_ec_check_demo.xml',
    # ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    # 'post_init_hook': '_post_init_hook',  # Comentado temporalmente
}
