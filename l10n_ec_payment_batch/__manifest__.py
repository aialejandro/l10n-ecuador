# -*- coding: utf-8 -*-
{
    'name': 'Ecuador Payment Batch',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Payment Batch Management for Ecuador',
    'description': """
Ecuador Payment Batch
=====================
This module provides payment batch functionality for Ecuador localization.

Features:
---------
* Create and manage payment batches
* Allocate payments to multiple invoices
* Track payment reconciliation
* Batch payment processing
* Partner payment grouping
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'l10n_ec',
        'l10n_ec_check',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_ec_payment_batch_sequences.xml',
        'views/l10n_ec_payment_batch_views.xml',
        'views/account_payment_views.xml',
        'wizard/l10n_ec_payment_batch_reconcile_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
