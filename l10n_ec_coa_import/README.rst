===============================
Ecuador custom COA import (BETA)
===============================

This module provides the groundwork for importing a custom chart of accounts for
Ecuadorian companies from an XLSX template. The wizard currently supports
reading accounts from a minimal template (code, name, account type), inferring
the required account groups and reconciliation flags, creating them for a
company, and exposing the most common default-account settings.

The review step highlights whether the target company already has accounts or a
chart template assigned. You can enable *Override Existing Chart* to wipe those
defaults automatically as long as no journal entries exist yet for the company.

.. warning::

   The automated cloning of taxes, fiscal positions, journals, and other
   localization data is not implemented yet. This iteration focuses on the
   interactive wizard and data validation scaffolding.
