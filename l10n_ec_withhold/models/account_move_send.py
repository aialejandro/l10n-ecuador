# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _get_default_pdf_report_id(self, move):
        # Withholding moves should use the dedicated withholding report instead of the invoice one.
        if move.l10n_latam_document_type_id.internal_type == 'withhold':
            withhold_report = self.env.ref('l10n_ec_withhold.action_report_withholding_ec', raise_if_not_found=False)
            if withhold_report:
                return withhold_report

        return super()._get_default_pdf_report_id(move)

    @api.model
    def _check_move_constrains(self, moves):
        # Allow withholding moves to bypass the sales-document constraint.
        non_withhold_moves = moves.filtered(lambda m: m.l10n_latam_document_type_id.internal_type != 'withhold')
        if non_withhold_moves:
            super()._check_move_constrains(non_withhold_moves)

        # Still check posted state for all moves including withholdings.
        from odoo.exceptions import UserError
        from odoo import _
        if any(move.state != 'posted' for move in moves):
            raise UserError(_("You can't generate invoices that are not posted."))
