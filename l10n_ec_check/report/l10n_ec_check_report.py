# -*- coding: utf-8 -*-

from odoo import models, api


class ReportCheckPrint(models.AbstractModel):
    _name = 'report.l10n_ec_check.report_check_print'
    _description = 'Reporte de Impresión de Cheques Ecuador'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Obtener valores para el reporte de cheques
        """
        checks = self.env['l10n_latam.check'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'l10n_latam.check',
            'docs': checks,
            'data': data,
        }
