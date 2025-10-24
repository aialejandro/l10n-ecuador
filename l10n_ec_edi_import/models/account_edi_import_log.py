# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountEdiImportLog(models.Model):
    """Granular audit entry generated per processed document."""

    _name = "account.edi.import.log"
    _description = "EDI Import Log"
    _order = "create_date desc"

    session_id = fields.Many2one(
        "account.edi.import.session",
        string="Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    status = fields.Selection(
        [
            ("success", "Success"),
            ("warning", "Warning"),
            ("error", "Error"),
            ("skipped", "Skipped"),
        ],
        required=True,
        default="success",
        index=True,
    )
    document_code = fields.Char(string="Document Code", size=4)
    document_type = fields.Char(string="Document Type")
    document_number = fields.Char(string="Document Number", index=True)
    access_key = fields.Char(string="Access Key", size=49, index=True)
    issue_date = fields.Date(string="Issue Date")
    amount_total = fields.Monetary(string="Total", currency_field="company_currency_id")
    partner_id = fields.Many2one(
        "res.partner", string="Partner", index=True, ondelete="set null"
    )
    partner_vat = fields.Char(string="Partner VAT")
    company_id = fields.Many2one(
        related="session_id.company_id", store=True, index=True
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", store=True
    )
    message = fields.Text(string="Message")
    processing_time = fields.Float(string="Processing Time (s)")
    payload = fields.Text(string="Raw Payload")
    target_model = fields.Char(string="Created Model")
    target_res_id = fields.Integer(string="Record ID")

    def action_open_target(self):
        self.ensure_one()
        if not (self.target_model and self.target_res_id):
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.target_model,
            "view_mode": "form",
            "res_id": self.target_res_id,
            "target": "current",
        }

    @api.model
    def create_from_result(self, session, result):
        """Persist helper using a normalized data dictionary."""

        vals = {
            "session_id": session.id,
            "status": result.get("status", "error"),
            "document_code": result.get("document_code"),
            "document_type": result.get("document_type"),
            "document_number": result.get("document_number"),
            "access_key": result.get("access_key"),
            "issue_date": result.get("issue_date"),
            "amount_total": result.get("amount_total"),
            "partner_id": result.get("partner_id"),
            "partner_vat": result.get("partner_vat"),
            "message": result.get("message"),
            "processing_time": result.get("processing_time", 0.0),
            "payload": result.get("payload"),
            "target_model": result.get("target_model"),
            "target_res_id": result.get("target_res_id"),
        }
        return self.create(vals)
