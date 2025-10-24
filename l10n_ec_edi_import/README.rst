=========================
Ecuador EDI Import (CE)
=========================

Overview
========

This module provides the foundation for importing Ecuadorian electronic documents in Odoo Community Edition v18.
It introduces session tracking, document-level audit logs, and integration hooks for SRI SOAP services. The
wizard currently supports XML uploads and TXT files containing SRI access keys. TXT imports rely on the
authorization service to retrieve the full XML payload before processing.

Contributing
============

* Place any sample XML/TXT payloads or reference documents inside ``docs/examples`` before starting development.
* Execute the import wizard under Accounting ▸ EC EDI Imports. Each run persists an import session with detailed logs.
* Extend the document factories in ``wizard/l10n_ec_edi_import_wizard.py`` when new document types or creation rules are required.

