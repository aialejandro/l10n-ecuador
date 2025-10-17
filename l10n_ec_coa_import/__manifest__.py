# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Ecuador - Custom Chart of Accounts Import",
    "summary": "Import customized COA variants for Ecuadorian companies",
    "description": """\
This module provides an interactive wizard that lets Ecuadorian companies
bootstrap a custom chart of accounts from an XLSX template. The wizard also
clones the rest of the localization data (taxes, fiscal positions, journals,
configuration defaults) from the official l10n_ec packages while keeping track
of their origins.
""",
    "category": "Accounting/Localizations",
    "version": "18.0.2.0.0",
    "author": "aialejandro",
    "website": "https://github.com/aialejandro/l10n-ecuador",
    "license": "OEEL-1",
    "depends": [
        "account",
        "l10n_ec",
        "l10n_ec_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/coa_import_actions.xml",
        "views/coa_import_wizard_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
