import copy
import re
import uuid
from collections import OrderedDict

from odoo import api, fields, models

COMPANY_PLACEHOLDER = "__COMPANY__"


class L10nEcChartTemplate(models.Model):
    _name = "l10n.ec.chart.template"
    _description = "Custom Ecuador Chart Template"
    _order = "create_date desc"

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=1000)
    country_id = fields.Many2one("res.country", required=True, default=lambda self: self.env.ref("base.ec"))
    visible = fields.Boolean(default=True)
    payload = fields.Json(required=True, default=dict)
    source_filename = fields.Char()
    company_ids = fields.Many2many("res.company", string="Companies")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("l10n_ec_chart_template_code_uniq", "unique(code)", "Each custom chart template must have a unique code."),
    ]

    def _export_payload_for_company(self, company):
        self.ensure_one()
        payload = copy.deepcopy(self.payload or {})
        template_section = payload.setdefault("template_data", {})
        template_section.setdefault(self.code, {})
        company_section = payload.get("res.company") or {}
        mapped = {}
        for key, values in company_section.items():
            if key == COMPANY_PLACEHOLDER:
                mapped[company.id] = values
                continue
            if isinstance(key, int):
                mapped[key] = values
                continue
            if isinstance(key, str) and key.isdigit():
                mapped[int(key)] = values
                continue
            mapped[key] = values
        if not mapped and company_section:
            mapped[company.id] = next(iter(company_section.values()))
        if not mapped:
            mapped[company.id] = {}
        payload["res.company"] = mapped

        # Sanitize obsolete keys that may be present in stored payloads
        for values in (payload.get("account.group") or {}).values():
            values.pop("sequence", None)
        equity_unaffected_seen = False
        for account in (payload.get("account.account") or {}).values():
            if account.get("account_type") == "equity_unaffected":
                if equity_unaffected_seen:
                    account["account_type"] = "equity"
                else:
                    equity_unaffected_seen = True

        # Ensure critical models are ordered so dependencies load without failing
        priority_sequence = [
            "template_data",
            "res.company",
            "account.group",
            "account.account",
            "account.tax.group",
            "account.tax",
            "account.journal",
            "account.fiscal.position",
            "account.reconcile.model",
        ]
        ordered_payload = OrderedDict()
        for key in priority_sequence:
            if key in payload:
                ordered_payload[key] = payload[key]
        for key, value in payload.items():
            if key not in ordered_payload:
                ordered_payload[key] = value
        return ordered_payload

    @api.model
    def generate_code(self, base="ec_custom"):
        token = uuid.uuid4().hex[:8]
        base_slug = re.sub(r"[^0-9a-zA-Z]+", "_", (base or "ec_custom").lower()).strip("_") or "ec_custom"
        return f"{base_slug}_{token}"


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _get_chart_template_mapping(self, get_all=False):
        mapping = super()._get_chart_template_mapping(get_all=get_all)
        templates = self.env["l10n.ec.chart.template"].sudo().search([])
        if not get_all:
            templates = templates.filtered("visible")
        templates = templates.filtered("active")
        for template in templates:
            mapping[template.code] = {
                "name": template.name,
                "parent": False,
                "sequence": template.sequence or 1000,
                "country": template.country_id.code if template.country_id else "",
                "visible": bool(template.visible),
                "installed": True,
                "module": "l10n_ec_coa_import",
                "country_id": template.country_id.id if template.country_id else False,
            }
        return mapping

    def _get_chart_template_data(self, template_code):
        custom_template = self.env["l10n.ec.chart.template"].sudo().search([("code", "=", template_code)], limit=1)
        if not custom_template:
            return super()._get_chart_template_data(template_code)
        return custom_template._export_payload_for_company(self.env.company)
