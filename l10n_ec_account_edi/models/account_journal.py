from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ec_alternative_print_format = fields.Boolean(
        string="Formato de impresion alternativo",
        help="When enabled and no EDI format is configured in the journal, sale invoices use the alternative label in the standard invoice PDF.",
    )