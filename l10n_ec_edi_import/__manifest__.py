# -*- coding: utf-8 -*-
{
    "name": "Ecuador EDI Import",
    "summary": "Standalone utility to import Ecuadorian electronic documents.",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Odoo S.A.",
    "website": "https://www.odoo.com",
    "category": "Accounting/Localizations",
    "depends": [
        "account",
        "purchase",
        "l10n_ec",
        "l10n_ec_base",
        "l10n_ec_account_edi",
        "l10n_ec_withhold",
    ],
    "data": [
        "data/ir_sequence_data.xml",
        "security/ir.model.access.csv",
    "views/account_edi_import_session_views.xml",
    "views/account_edi_import_log_views.xml",
    "wizard/l10n_ec_edi_import_wizard_views.xml",
    "views/l10n_ec_edi_import_menu.xml",
    ],
    "demo": [],
    "application": False,
    "installable": True,
}
