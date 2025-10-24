# Development Notes for CoPilot

- Follow the latest Odoo 18 development guidelines when implementing features in this module.
- When testing installation, start with `-i l10n_ec_edi_import` on the database; once installed, use `-u l10n_ec_edi_import` for subsequent updates.
- Run the Odoo server via the virtual environment located at `venv`, targeting the `odoo18` database and configuration file `/etc/odoo18.conf` during test executions.
