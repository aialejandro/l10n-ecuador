from odoo import fields, models


class L10nEcTaxAccountMappingLine(models.TransientModel):
    _name = "l10n.ec.tax.account.mapping.line"
    _description = "Tax Account Mapping Line"
    _order = "original_code"

    wizard_id = fields.Many2one(
        "l10n.ec.coa.import.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    original_code = fields.Char(
        string="Original Account Code",
        required=True,
        readonly=True,
    )
    original_name = fields.Char(
        string="Original Account Name",
        readonly=True,
    )
    new_account_id = fields.Many2one(
        "account.account",
        string="New Account",
        domain="[('company_ids', 'in', [company_id])]",
    )
    company_id = fields.Many2one(
        "res.company",
        related="wizard_id.company_id",
        store=True,
    )
