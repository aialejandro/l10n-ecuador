# -*- coding: utf-8 -*-

from odoo import fields, models


class ResBankRelatedLine(models.Model):
    _name = "l10n.ec.bank.related.line"
    _description = "Banco Relacionado"
    _order = "id"

    bank_id = fields.Many2one(
        "res.bank",
        string="Banco Principal",
        required=True,
        ondelete="cascade",
    )
    related_bank_id = fields.Many2one(
        "res.bank",
        string="Banco",
        required=True,
        ondelete="restrict",
    )
    code = fields.Char(string="Codigo")

    _sql_constraints = [
        (
            "unique_related_bank_per_bank",
            "unique(bank_id, related_bank_id)",
            "No se puede repetir el mismo banco en la pestana de bancos relacionados.",
        ),
    ]
