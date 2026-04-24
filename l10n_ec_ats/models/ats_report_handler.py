# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_repr, groupby
from odoo.addons.l10n_ec.models.res_partner import PartnerIdTypeEc


SALE_DOCUMENT_CODES = ["01", "02", "03", "04", "05"]
LOCAL_PURCHASE_DOCUMENT_CODES = ["01", "02", "03", "04", "05", "09", "11", "12", "19", "20", "21", "43", "45", "47", "48"]
ATS_SALE_DOCUMENT_TYPE = {
    "01": "18",
    "02": "18",
}
VAT_NOT_ZERO_PREFIX = "vat"
ATS_PAYMENT_FORM_AMOUNT_LIMIT = 500.0
L10N_EC_VAT_TAX_NOT_ZERO_GROUPS = (
    "vat05",
    "vat08",
    "vat12",
    "vat13",
    "vat14",
    "vat15",
)
ATS_PURCHASE_TAX_SUPPORT_FALLBACK = "01"
ATS_AIR_CODE_ALIASES = {
    "304": "304A",
    "304B": "304A",
    "3482": "303A",
}
ATS_AIR_PERCENTAGE_OVERRIDES = {
    "303A": 3.0,
    "309": 2.75,
    "312": 1.75,
    "3440": 2.75,
}


class L10nECTaxReportATSCustomHandler(models.AbstractModel):
    _name = "l10n.ec.ats.helper"
    _description = "ATS Helper for Ecuador Localization"

    def _generate_ats(self, options):
        company = self.env.company
        if company.account_fiscal_country_id.code != "EC":
            raise ValidationError(_("This report is only available for Ecuadorian companies."))

        date_start = fields.Date.to_date(options["date"]["date_from"])
        date_finish = fields.Date.to_date(options["date"]["date_to"])

        sale_journals = self.env["account.journal"].search([
            ("type", "=", "sale"),
            ("company_id", "=", company.id),
            ("l10n_ec_entity", "!=", False),
        ])
        num_estab_ruc = len(set(sale_journals.mapped("l10n_ec_entity")))

        values = {
            "company": company,
            "company_legal_name": getattr(company, "l10n_ec_legal_name", False) or company.name or "",
            "latam_identification_type": self._l10n_ec_get_ats_identification_type_code(company.partner_id.l10n_latam_identification_type_id),
            "anio": date_finish.year,
            "mes": f"{date_finish.month:02}",
            "num_estab_ruc": f"{num_estab_ruc:03}",
            "format_float": self._l10n_ec_ats_format_float,
        }

        purchase_vals, purchase_errors = self._get_purchase_values(date_start, date_finish)
        sale_vals, sale_errors = self._get_sale_values(date_start, date_finish)
        void_moves = self._get_void_moves(date_start, date_finish, sale_journals)

        values.update({
            "purchase_vals": purchase_vals,
            "void_moves": void_moves,
            **sale_vals,
        })
        errors = purchase_errors + sale_errors

        return self.env["ir.qweb"]._render("l10n_ec_ats.ats_report_template", values), errors

    @api.model
    def _get_purchase_values(self, date_start, date_finish):
        def get_authorization_number(move):
            auth = move._l10n_ec_get_ats_authorization_number()
            return auth or "9999999999"

        def is_reimbursement_tax(tax):
            return "REIMB" in (tax.name or "").upper() or "REEMB" in (tax.name or "").upper()

        def get_ec_type(taxes):
            return (taxes & ec_vat_taxes).tax_group_id.l10n_ec_type or "zero_vat"

        def get_taxsupport(taxes):
            ec_taxes = taxes & ec_vat_taxes
            if not ec_taxes:
                return "02"
            if "l10n_ec_code_taxsupport" in ec_taxes._fields:
                return ec_taxes[:1].l10n_ec_code_taxsupport or "02"
            return "02"

        def get_invoice_line_taxsupport(line):
            return (
                getattr(line, "l10n_ec_tax_support", False)
                or getattr(line.move_id, "l10n_ec_tax_support", False)
                or get_taxsupport(line.tax_ids)
            )

        def get_tax_line_taxsupport(line):
            return (
                getattr(line, "l10n_ec_tax_support", False)
                or getattr(line.move_id, "l10n_ec_tax_support", False)
                or get_taxsupport(line.tax_line_id)
            )

        ec_vat_taxes = self.env["account.tax"].with_context(active_test=False).search([
            ("tax_group_id.l10n_ec_type", "not in", (False, "ice", "irbpnr", "other")),
            ("company_id", "=", self.env.company.id),
        ])

        errors = []
        purchase_invoices = self.env["account.move"].search([
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("l10n_latam_document_type_id.code", "in", LOCAL_PURCHASE_DOCUMENT_CODES),
            ("date", ">=", date_start),
            ("date", "<=", date_finish),
            ("company_id", "=", self.env.company.id),
        ], order="invoice_date, move_type, l10n_latam_document_type_id, create_date")

        purchase_vals = []
        for in_inv in purchase_invoices:
            invoice_lines = in_inv.invoice_line_ids.filtered(
                lambda line: line.display_type not in ("line_section", "line_note") and not any(is_reimbursement_tax(tax) for tax in line.tax_ids)
            )

            sign = 1 if in_inv.move_type == "in_invoice" else -1
            base_amounts = defaultdict(
                lambda: defaultdict(int),
                {
                    taxsupport: defaultdict(
                        int,
                        {
                            ec_type: sign * sum(abs(base_line.price_subtotal or base_line.balance) for base_line in base_lines_per_ec_type)
                            for ec_type, base_lines_per_ec_type in groupby(base_lines_per_taxsupport, lambda l: get_ec_type(l.tax_ids))
                        },
                    )
                    for taxsupport, base_lines_per_taxsupport in groupby(invoice_lines, get_invoice_line_taxsupport)
                },
            )

            tax_lines = in_inv.line_ids.filtered(lambda line: line.tax_line_id & ec_vat_taxes and not is_reimbursement_tax(line.tax_line_id))
            tax_amounts = defaultdict(
                lambda: defaultdict(int),
                {
                    taxsupport: defaultdict(
                        int,
                        {
                            ec_type: sign * sum(abs(tax_line.balance) for tax_line in tax_lines_per_ec_type)
                            for ec_type, tax_lines_per_ec_type in groupby(tax_lines_per_taxsupport, lambda l: get_ec_type(l.tax_line_id))
                        },
                    )
                    for taxsupport, tax_lines_per_taxsupport in groupby(tax_lines, get_tax_line_taxsupport)
                },
            )

            transaction_type = PartnerIdTypeEc.get_ats_code_for_partner(in_inv.partner_id, in_inv.move_type).value
            id_prov, validation_errors = self._l10n_ec_get_validated_partner_vat(in_inv.partner_id)
            errors += validation_errors
            estab_inv, emision_inv, secuencial_inv = self._l10n_ec_get_document_number_vals(in_inv)

            inv_values = {
                "tpIdProv": transaction_type,
                "idProv": id_prov,
                "tipoComprobante": self._get_l10n_latam_ats_document_code(in_inv),
                "parteRel": "SI" if getattr(in_inv.commercial_partner_id, "l10n_ec_related_party", False) else "NO",
                "fechaRegistro": in_inv.date.strftime("%d/%m/%Y"),
                "establecimiento": estab_inv,
                "puntoEmision": emision_inv,
                "secuencial": secuencial_inv,
                "fechaEmision": in_inv.invoice_date.strftime("%d/%m/%Y") if in_inv.invoice_date else "",
                "autorizacion": get_authorization_number(in_inv),
                "totbasesImpReemb": 0.0,
            }

            inv_values.update(self._l10n_ec_get_ats_payment_exterior_values(in_inv))

            formas_de_pago = self._l10n_ec_get_ats_payment_forms(in_inv)
            if formas_de_pago:
                inv_values["formasDePago"] = formas_de_pago

            if transaction_type == "03":
                supplier_id_type_getter = getattr(
                    in_inv.commercial_partner_id,
                    "_get_l10n_ec_edi_supplier_identification_type_code",
                    None,
                )
                inv_values.update({
                    "tipoProv": supplier_id_type_getter() if supplier_id_type_getter else ("02" if in_inv.commercial_partner_id.is_company else "01"),
                    "denoProv": self._l10n_ec_get_normalized_name(in_inv.partner_id.commercial_company_name or in_inv.partner_id.name),
                })

            if in_inv.l10n_latam_document_type_id.code in ("04", "05"):
                modified_move = in_inv.reversed_entry_id or in_inv.debit_origin_id
                if modified_move:
                    estab_mod, emision_mod, secuencial_mod = self._l10n_ec_get_document_number_vals(modified_move)
                    inv_values.update({
                        "docModificado": modified_move.l10n_latam_document_type_id.code or "",
                        "estabModificado": estab_mod,
                        "ptoEmiModificado": emision_mod,
                        "secModificado": secuencial_mod,
                        "autModificado": get_authorization_number(modified_move),
                    })

            for taxsupport in base_amounts:
                values = inv_values.copy()
                vat_not_zero_types = [
                    ec_type
                    for ec_type in L10N_EC_VAT_TAX_NOT_ZERO_GROUPS
                    if ec_type in base_amounts[taxsupport]
                ]
                values.update({
                    "codSustento": taxsupport if taxsupport != "02" else ATS_PURCHASE_TAX_SUPPORT_FALLBACK,
                    "baseNoGraIva": base_amounts[taxsupport]["not_charged_vat"],
                    "baseImponible": base_amounts[taxsupport]["zero_vat"],
                    "baseImpGrav": sum(base_amounts[taxsupport].get(ec_type, 0.0) for ec_type in vat_not_zero_types),
                    "baseImpExe": base_amounts[taxsupport]["exempt_vat"],
                    "montoIva": sum(tax_amounts[taxsupport].get(ec_type, 0.0) for ec_type in vat_not_zero_types),
                    "valRetBien10": 0.0,
                    "valRetServ20": 0.0,
                    "valorRetBienes": 0.0,
                    "valRetServ50": 0.0,
                    "valorRetServicios": 0.0,
                    "valRetServ100": 0.0,
                    "valorRetencionNc": 0.0,
                })

                withhold_lines = self._l10n_ec_get_ats_related_withhold_lines(in_inv, taxsupport)
                withhold_amounts = defaultdict(float)
                income_withhold_lines = self.env["account.move.line"]
                withhold_move = self.env["account.move"]

                for withhold_line in withhold_lines:
                    tax = withhold_line.tax_ids[:1]
                    if not tax:
                        continue

                    withhold_move |= withhold_line.move_id
                    raw_amount = self._l10n_ec_get_ats_withhold_amount(withhold_line, tax)
                    if tax.tax_group_id.l10n_ec_type == "withhold_income_purchase":
                        income_withhold_lines |= withhold_line
                    else:
                        withhold_amounts[tax.l10n_ec_code_applied] += raw_amount

                is_credit_note = in_inv.l10n_latam_document_type_id.internal_type == "credit_note"
                values.update({
                    "valRetBien10": withhold_amounts.get("721", 0.0),
                    "valRetServ20": withhold_amounts.get("723", 0.0),
                    "valorRetBienes": withhold_amounts.get("725", 0.0),
                    "valRetServ50": withhold_amounts.get("727", 0.0),
                    "valorRetServicios": withhold_amounts.get("729", 0.0),
                    "valRetServ100": withhold_amounts.get("731", 0.0),
                    "valorRetencionNc": sum(withhold_amounts.values()) if is_credit_note else 0.0,
                })

                if withhold_move:
                    values.update(self._l10n_ec_get_ats_withhold_document_vals(withhold_move[:1], get_authorization_number))

                air_vals = []
                if income_withhold_lines:
                    grouped_air_vals = defaultdict(lambda: {
                        "baseImpAir": 0.0,
                        "porcentajeAir": 0.0,
                        "valRetAir": 0.0,
                    })
                    for withhold_line in income_withhold_lines:
                        tax = withhold_line.tax_ids[:1]
                        if not tax:
                            continue

                        ats_code, ats_percentage = self._l10n_ec_get_ats_air_code_and_percentage(tax, withhold_line)
                        grouped_air_vals[ats_code]["baseImpAir"] += abs(withhold_line.price_subtotal or withhold_line.balance)
                        grouped_air_vals[ats_code]["porcentajeAir"] = ats_percentage
                        grouped_air_vals[ats_code]["valRetAir"] += self._l10n_ec_get_ats_withhold_amount(withhold_line, tax, ats_percentage)

                    air_vals = [
                        {
                            "codRetAir": ats_code,
                            **vals,
                        }
                        for ats_code, vals in sorted(grouped_air_vals.items())
                    ]
                else:
                    default_air_base = values["baseImponible"] + values["baseImpGrav"]
                    if default_air_base:
                        air_vals = [{
                            "codRetAir": "332",
                            "baseImpAir": abs(default_air_base),
                            "porcentajeAir": 0.0,
                            "valRetAir": 0.0,
                        }]

                if air_vals:
                    values["air_vals"] = air_vals

                purchase_vals.append(values)

        return purchase_vals, errors

    @api.model
    def _l10n_ec_ats_round(self, amount, precision="0.01"):
        quant = Decimal(precision)
        return float(Decimal(str(amount or 0.0)).quantize(quant, rounding=ROUND_HALF_EVEN))

    @api.model
    def _l10n_ec_ats_format_float(self, amount):
        return float_repr(self._l10n_ec_ats_round(amount), 2)

    @api.model
    def _l10n_ec_get_ats_payment_forms(self, move):
        move.ensure_one()
        if abs(move.amount_total) < ATS_PAYMENT_FORM_AMOUNT_LIMIT:
            return []

        payment_data_getter = getattr(move, "_l10n_ec_get_payment_data", None)
        if not payment_data_getter:
            return []

        payment_forms = []
        for payment_vals in payment_data_getter() or []:
            payment_code = payment_vals.get("formaPago") or payment_vals.get("payment_code")
            if payment_code and payment_code not in payment_forms:
                payment_forms.append(payment_code)
        return payment_forms

    @api.model
    def _l10n_ec_get_ats_payment_exterior_values(self, move):
        move.ensure_one()
        country = move.commercial_partner_id.country_id
        if country and country.code != "EC":
            ats_country_code = getattr(country, "l10n_ec_code_ats", False) or "NA"
            return {
                "tipoRegi": "01",
                "paisEfecPagoGen": ats_country_code,
                "pagoLocExt": "02",
                "paisEfecPago": ats_country_code,
                "aplicConvDobTrib": "NO",
                "pagExtSujRetNorLeg": "NO",
            }

        return {
            "pagoLocExt": "01",
            "paisEfecPago": "NA",
            "aplicConvDobTrib": "NA",
            "pagExtSujRetNorLeg": "NA",
        }

    @api.model
    def _l10n_ec_get_ats_related_withhold_lines(self, move, taxsupport):
        move.ensure_one()
        return move.l10n_ec_withhold_ids.l10n_ec_withhold_line_ids.filtered(
            lambda line: (
                line.l10n_ec_invoice_withhold_id == move
                and line.move_id.state == "posted"
                and line.tax_ids
                and (line.l10n_ec_tax_support or line.move_id.l10n_ec_tax_support or "02") == taxsupport
            )
        )

    @api.model
    def _l10n_ec_get_ats_withhold_amount(self, withhold_line, tax, percentage=None):
        applied_percentage = abs(
            percentage
            if percentage is not None
            else (getattr(withhold_line, "l10n_ec_withhold_tax_percentage", 0.0) or tax.amount or 0.0)
        )
        line_base_amount = abs(withhold_line.price_subtotal or withhold_line.balance)
        return float(Decimal(str(line_base_amount)) * Decimal(str(applied_percentage)) / Decimal("100"))

    @api.model
    def _l10n_ec_get_ats_air_code_and_percentage(self, tax, withhold_line=None):
        tax.ensure_one()
        ats_code = tax.l10n_ec_code_ats or "NA"
        normalized_code = ATS_AIR_CODE_ALIASES.get(ats_code, ats_code)
        stored_percentage = abs(getattr(withhold_line, "l10n_ec_withhold_tax_percentage", 0.0) or 0.0)
        percentage = stored_percentage or ATS_AIR_PERCENTAGE_OVERRIDES.get(normalized_code, abs(tax.amount or 0.0))
        return normalized_code, percentage

    @api.model
    def _l10n_ec_get_ats_withhold_document_vals(self, withhold, get_authorization_number):
        withhold.ensure_one()
        withhold_number = withhold.ref or withhold.l10n_latam_document_number or withhold.name or ""
        estab_ret, emision_ret, secuencial_ret = self._l10n_ec_get_number_vals(withhold_number)
        withhold_date = (
            (withhold.l10n_ec_authorization_date and withhold.l10n_ec_authorization_date.date())
            or (withhold.create_date and withhold.create_date.date())
            or withhold.invoice_date
            or withhold.date
        )
        return {
            "estabRetencion1": estab_ret,
            "ptoEmiRetencion1": emision_ret,
            "secRetencion1": secuencial_ret,
            "autRetencion1": get_authorization_number(withhold),
            "fechaEmiRet1": withhold_date.strftime("%d/%m/%Y") if withhold_date else "",
        }

    def _get_void_moves(self, date_start, date_finish, journals):
        void_invoices = self.env["account.move"].search([
            ("move_type", "in", self.env["account.move"].get_invoice_types()),
            ("state", "=", "cancel"),
            ("name", "not in", ("/", False)),
            ("l10n_latam_document_type_id.code", "in", SALE_DOCUMENT_CODES + LOCAL_PURCHASE_DOCUMENT_CODES),
            ("date", ">=", date_start),
            ("date", "<=", date_finish),
            ("company_id", "=", self.env.company.id),
        ], order="invoice_date, move_type, l10n_latam_document_type_id, create_date")
        return void_invoices.filtered(lambda m: m.journal_id.l10n_ec_require_emission)

    @api.model
    def _get_sale_values(self, date_start, date_finish):
        total_sales = 0.0
        invoices_values, errors = self._get_invoices_values(date_start, date_finish)
        sale_vals, sales_info_errors = self._get_sales_info_by_partner(invoices_values)
        errors += sales_info_errors

        values = {}
        if sale_vals:
            for id_partner in sale_vals:
                if sale_vals[id_partner]["tipoEmision"] == "F":
                    total_sales += sale_vals[id_partner]["amount_untaxed_signed"]

            sale_journals = self.env["account.journal"].search([
                ("type", "=", "sale"),
                ("company_id", "=", self.env.company.id),
                ("l10n_ec_entity", "!=", False),
            ])
            entities = list(set(sale_journals.mapped("l10n_ec_entity")))
            entities.sort()

            values.update({
                "sale_vals": sale_vals,
                "entities": entities,
                "total_entity_vals": self._l10n_ec_get_total_by_entity(invoices_values),
            })

        values.update({"total_sales": "{0:.2f}".format(total_sales)})
        return values, errors

    @api.model
    def _get_invoices_values(self, date_start, date_finish):
        def get_ec_type(taxes):
            return (taxes & ec_vat_taxes).tax_group_id.l10n_ec_type or "zero_vat"

        ec_vat_taxes = self.env["account.tax"].with_context(active_test=False).search([
            ("tax_group_id.l10n_ec_type", "not in", (False, "ice", "irbpnr", "other")),
            ("company_id", "=", self.env.company.id),
        ])

        errors = []
        invoices = self.env["account.move"].search([
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("l10n_latam_document_type_id.code", "in", SALE_DOCUMENT_CODES),
            ("date", ">=", date_start),
            ("date", "<=", date_finish),
            ("company_id", "=", self.env.company.id),
        ], order="partner_id, l10n_latam_document_type_id, invoice_date, create_date")

        invoices_values = []
        error_template = _("%s: Invoice lines should have exactly one VAT tax.")
        for invoice in invoices:
            invoice_lines = invoice.invoice_line_ids.filtered(lambda line: line.display_type not in ("line_section", "line_note"))
            if any(len(l.tax_ids & ec_vat_taxes) != 1 for l in invoice_lines):
                errors.append(error_template % invoice.name)

            sign = -1 if invoice.move_type == "out_invoice" else 1
            base_amounts = defaultdict(int, {
                ec_type: sign * sum(base_line.balance for base_line in base_lines)
                for ec_type, base_lines in groupby(invoice_lines, lambda l: get_ec_type(l.tax_ids))
            })
            tax_lines = invoice.line_ids.filtered(lambda l: l.tax_line_id & ec_vat_taxes)
            tax_amounts = defaultdict(int, {
                ec_type: sign * sum(tax_line.balance for tax_line in tax_lines)
                for ec_type, tax_lines in groupby(tax_lines, lambda l: get_ec_type(l.tax_line_id))
            })

            auth = invoice._l10n_ec_get_ats_authorization_number()
            is_manual = bool(auth and len(auth) == 10)
            emission_type = "F" if is_manual else "E"
            vat_not_zero_types = [k for k in base_amounts.keys() if str(k).startswith(VAT_NOT_ZERO_PREFIX)]

            invoice_vals = {
                "move": invoice,
                "move_type": invoice.move_type,
                "partner": invoice.partner_id,
                "latam_document_type_code": invoice.l10n_latam_document_type_id.code,
                "entity_point": invoice.journal_id.l10n_ec_entity,
                "l10n_latam_document_number": invoice.l10n_latam_document_number,
                "journal_entity": invoice.journal_id.l10n_latam_use_documents and invoice.journal_id.active,
                "tipoComprobante": self._get_l10n_latam_ats_document_code(invoice),
                "tipoEmision": emission_type,
                "baseNoGraIva": base_amounts["exempt_vat"] + base_amounts["not_charged_vat"],
                "baseImponible": base_amounts["zero_vat"],
                "baseImpGrav": sum(base_amounts.get(ec_type, 0.0) for ec_type in vat_not_zero_types),
                "montoIva": sum(tax_amounts.get(ec_type, 0.0) for ec_type in vat_not_zero_types),
                "amount_untaxed_signed": invoice.amount_untaxed_signed,
            }
            invoices_values.append(invoice_vals)
        return invoices_values, errors

    @api.model
    def _get_sales_info_by_partner(self, invoices_values):
        group_sales = {}
        errors = []

        for id_partner, partner_invoices_values in groupby(invoices_values, key=lambda m: (m["partner"].commercial_partner_id, m["latam_document_type_code"], m["tipoEmision"])):
            partner = partner_invoices_values[0]["partner"]
            identification_type_code = PartnerIdTypeEc.get_ats_code_for_partner(partner, "out_").value
            id_cliente, validation_errors = self._l10n_ec_get_validated_partner_vat(partner)
            errors += validation_errors

            values = {
                "numeroComprobantes": len(partner_invoices_values),
                "tipoComprobante": partner_invoices_values[0]["tipoComprobante"],
                "tipoEmision": partner_invoices_values[0]["tipoEmision"],
                "compensaciones": {"tipoCompe": "0", "monto": 0},
                "tpIdCliente": identification_type_code or "",
                "idCliente": id_cliente or "",
                "valorRetIva": 0.0,
                "valorRetRenta": 0.0,
                "baseNoGraIva": sum(v["baseNoGraIva"] for v in partner_invoices_values),
                "baseImponible": sum(v["baseImponible"] for v in partner_invoices_values),
                "baseImpGrav": sum(v["baseImpGrav"] for v in partner_invoices_values),
                "montoIva": sum(v["montoIva"] for v in partner_invoices_values),
                "amount_untaxed_signed": sum(v["amount_untaxed_signed"] for v in partner_invoices_values),
            }

            if identification_type_code in ["04", "05", "06"] and any(v["tipoComprobante"] in ["18", "04", "05", "44"] for v in partner_invoices_values):
                values.update({"parteRelVtas": "NO"})

            if identification_type_code == "06":
                values.update({
                    "tipoCliente": "02" if partner.is_company else "01",
                    "denoCli": partner.commercial_partner_id.commercial_company_name or partner.commercial_partner_id.name,
                })
            group_sales[id_partner] = values
        return group_sales, errors

    @api.model
    def _l10n_ec_get_ats_identification_type_code(self, identificaction_type):
        id_types_by_xmlid = {
            "l10n_ec.ec_dni": "C",
            "l10n_ec.ec_ruc": "R",
            "l10n_ec.ec_passport": "P",
            "l10n_latam_base.it_pass": "P",
            "l10n_latam_base.it_fid": "P",
            "l10n_latam_base.it_vat": "P",
        }
        ats_id_type_code = ""
        xmlid_by_res_id = {
            self.env["ir.model.data"]._xmlid_to_res_model_res_id(xmlid, raise_if_not_found=True)[1]: xmlid
            for xmlid in id_types_by_xmlid
        }
        id_type_xmlid = xmlid_by_res_id.get(identificaction_type.id)
        if id_type_xmlid in id_types_by_xmlid:
            ats_id_type_code = id_types_by_xmlid[id_type_xmlid]
        if identificaction_type.country_id.code != "EC":
            ats_id_type_code = "P"
        return ats_id_type_code

    @api.model
    def _l10n_ec_get_total_by_entity(self, invoices_values):
        entity_totals = defaultdict(lambda: {"total": 0.0, "ivaComp": 0.0})
        for invoice_values in invoices_values:
            if invoice_values["tipoEmision"] == "F":
                entity_point = invoice_values["entity_point"]
                invoice_subtotal = invoice_values["baseImponible"] + invoice_values["baseImpGrav"]
                invoice_subtotal = invoice_subtotal * (1 if invoice_values["move_type"] == "out_invoice" else -1)
                entity_totals[entity_point]["total"] += invoice_subtotal
        return entity_totals

    @api.model
    def _l10n_ec_get_validated_partner_vat(self, partner):
        errors = []
        partner_vat = partner.commercial_partner_id.vat
        ec_id_type = partner._l10n_ec_get_identification_type()
        if (partner_vat and len(partner_vat) < 3) or not partner_vat:
            errors.append(_("The identification number of contact %s must have at least 3 characters.", partner.name))
        elif ec_id_type in ["passport", "ec_passport", "foreign"]:
            partner_vat = (partner_vat and partner_vat[:13]) or ""
        elif not ec_id_type:
            errors.append(_(
                'Valid types of identification for the ATS report are: Cédula, Ruc, Passport, Foreign ID. Contact %(partner)s has type "%(type)s".',
                partner=partner.name,
                type=partner.l10n_latam_identification_type_id.name,
            ))
        return partner_vat, errors

    def _l10n_ec_get_document_number_vals(self, move):
        move.ensure_one()
        estab, emision, sequential = self._l10n_ec_get_number_vals(move.l10n_latam_document_number)
        if estab + emision + sequential == "0" * 15 and move.country_code == "EC" and move.l10n_latam_document_number and not move.l10n_latam_document_type_id.l10n_ec_check_format:
            estab, emision, sequential = "999", "999", move.l10n_latam_document_number[-8:]
        return estab.zfill(3), emision.zfill(3), sequential.zfill(9)

    def _l10n_ec_get_number_vals(self, number):
        estab, emision, sequential = "", "", ""
        if number:
            num_match = re.match(r"(?:Ret )?(\d{1,3})-(\d{1,3})-(\d{1,9})", number.strip())
            if num_match:
                estab, emision, sequential = num_match.groups()
        return estab.zfill(3), emision.zfill(3), sequential.zfill(9)

    @api.model
    def _l10n_ec_get_normalized_name(self, name):
        def get_printable_ascii_text(text):
            mapping = {"ñ": "n", "Ñ": "N", "&": "Y", "_": " "}
            ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore")
            pattern = re.compile("|".join("(%s)" % re.escape(x) for x in mapping))
            ascii_replaced = pattern.sub(lambda m: mapping[m.group(0)], ascii_text.decode("utf-8"))
            return ascii_replaced.strip()

        text = name
        if text:
            for token in [".", ",", "-", "/", "(", ")", "´"]:
                text = text.replace(token, " ")
            text = get_printable_ascii_text(text)
        return text

    @api.model
    def _get_l10n_latam_ats_document_code(self, move):
        move.ensure_one()
        document_code = move.l10n_latam_document_type_id.code
        if move.is_sale_document() and ATS_SALE_DOCUMENT_TYPE.get(document_code, False):
            return ATS_SALE_DOCUMENT_TYPE[document_code]
        return document_code
