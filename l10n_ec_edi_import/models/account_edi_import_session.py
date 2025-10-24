# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class AccountEdiImportSession(models.Model):
    """Persisted execution context for an EDI import run."""

    _name = "account.edi.import.session"
    _description = "EDI Import Session"
    _order = "create_date desc"

    name = fields.Char(string="Session", required=True, default="/", copy=False)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Executed By",
        default=lambda self: self.env.user,
        required=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Completed"),
            ("failed", "Failed"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    start_date = fields.Datetime(string="Started At", readonly=True)
    end_date = fields.Datetime(string="Finished At", readonly=True)
    duration = fields.Float(
        string="Duration (minutes)", compute="_compute_duration", store=True
    )
    log_ids = fields.One2many(
        "account.edi.import.log",
        "session_id",
        string="Logs",
    )
    total_documents = fields.Integer(
        compute="_compute_counters", store=True, string="Documents"
    )
    success_count = fields.Integer(
        compute="_compute_counters", store=True, string="Success"
    )
    warning_count = fields.Integer(
        compute="_compute_counters", store=True, string="Warnings"
    )
    error_count = fields.Integer(
        compute="_compute_counters", store=True, string="Errors"
    )
    skipped_count = fields.Integer(
        compute="_compute_counters", store=True, string="Skipped"
    )
    note = fields.Text(string="Notes")

    @api.model
    def create(self, vals):
        if vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "account.edi.import.session"
            ) or "/"
        return super().create(vals)

    @api.depends("start_date", "end_date")
    def _compute_duration(self):
        for session in self:
            if session.start_date and session.end_date:
                delta = session.end_date - session.start_date
                session.duration = delta / timedelta(minutes=1)  # minutes as float
            else:
                session.duration = 0.0

    @api.depends("log_ids.status")
    def _compute_counters(self):
        for session in self:
            status_counts = {
                "success": 0,
                "warning": 0,
                "error": 0,
                "skipped": 0,
            }
            for log in session.log_ids:
                status_counts[log.status] = status_counts.get(log.status, 0) + 1
            session.success_count = status_counts.get("success", 0)
            session.warning_count = status_counts.get("warning", 0)
            session.error_count = status_counts.get("error", 0)
            session.skipped_count = status_counts.get("skipped", 0)
            session.total_documents = sum(status_counts.values())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def action_open_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Import Logs"),
            "res_model": "account.edi.import.log",
            "view_mode": "tree,form",
            "domain": [("session_id", "=", self.id)],
            "context": {"default_session_id": self.id},
        }

    def mark_running(self):
        self.write({"state": "running", "start_date": fields.Datetime.now()})

    def mark_done(self):
        self.write({"state": "done", "end_date": fields.Datetime.now()})

    def mark_failed(self, message=None):
        vals = {"state": "failed", "end_date": fields.Datetime.now()}
        if message:
            vals["note"] = message
        self.write(vals)
