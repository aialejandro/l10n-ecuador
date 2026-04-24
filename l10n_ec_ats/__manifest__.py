{
    "name": "Ecuador ATS for Dynamic Tax Report",
    "summary": "Exporta ATS XML desde el reporte dinamico de impuestos de Cybro",
    "category": "Accounting/Localizations/Reporting",
    "countries": ["ec"],
    "author": "Odoo-EC",
    "website": "https://github.com/OCA/l10n-ecuador",
    "license": "LGPL-3",
    "version": "18.0.1.0.0",
    "depends": ["dynamic_accounts_report", "l10n_ec_base", "l10n_ec_account_edi", "l10n_ec_withhold"],
    "data": [
        "data/ats_report.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ec_ats/static/src/xml/tax_report_ats_button.xml",
            "l10n_ec_ats/static/src/js/tax_report_ats_button.js"
        ]
    },
    "installable": True,
    "auto_install": False,
}
