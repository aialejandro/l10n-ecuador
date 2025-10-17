from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_open_l10n_ec_coa_import_wizard(self):
        self.ensure_one()
        return {
            "name": "Import Ecuadorian COA",
            "type": "ir.actions.act_window",
            "res_model": "l10n.ec.coa.import.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "l10n_ec_coa_import.view_l10n_ec_coa_import_wizard"
            ).id,
            "target": "new",
            "context": {
                "default_company_id": self.company_id.id,
            },
        }
