# -*- coding: utf-8 -*-
import base64
import logging
import re
import time
from collections import defaultdict
from datetime import datetime

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression  # type: ignore[import]

_logger = logging.getLogger(__name__)


SUPPORTED_DOC_TYPES = {
    "01": {
        "label": "Factura",
        "internal_type": "invoice",
        "move_type": "in_invoice",
        "latam_xml_id": "l10n_ec.ec_dt_01",
    },
    "03": {
        "label": "Liquidación de Compras",
        "internal_type": "purchase_liquidation",
        "move_type": "in_invoice",
        "latam_xml_id": "l10n_ec.ec_dt_03",
    },
    "04": {
        "label": "Nota de Crédito",
        "internal_type": "credit_note",
        "move_type": "in_refund",
        "latam_xml_id": "l10n_ec.ec_dt_04",
    },
    "07": {
        "label": "Comprobante de Retención",
        "internal_type": "withhold",
        "move_type": "entry",
        "latam_xml_id": "l10n_ec.ec_dt_07",
    },
}


class DocumentImportError(Exception):
    """Raised when a document cannot be processed."""


class DocumentParser:
    """Utility to convert SRI XML payloads into normalized dictionaries."""

    def __init__(self, company):
        self.company = company

    def parse(self, xml_bytes):
        payload = self._ensure_payload(xml_bytes)
        root = payload["root"]
        doc_code = self._value(root, "infoTributaria/codDoc")
        parsed = {
            "document_code": doc_code,
            "document_type": SUPPORTED_DOC_TYPES.get(doc_code, {}).get(
                "label", "Unknown"
            ),
            "access_key": payload.get("access_key")
            or self._value(root, "infoTributaria/claveAcceso"),
            "authorization": payload.get("authorization"),
            "authorization_date": payload.get("authorization_date"),
            "document_number": self._build_number(root),
            "partner": self._parse_partner(root),
            "issue_date": self._parse_date(self._value(root, self._date_node(doc_code))),
            "currency": self._value(root, "infoFactura/moneda") or "USD",
            "lines": self._parse_lines(root, doc_code),
            "totals": self._parse_totals(root, doc_code),
            "references": self._parse_references(root, doc_code),
            "environment": self._value(root, "infoTributaria/ambiente"),
            "sustento": self._parse_sustento(root, doc_code),
        }
        return parsed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _ensure_payload(self, xml_bytes):
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_bytes, parser=parser)
        tag = self._tag(root)
        if tag == "autorizacion":
            comprobante_node = root.find("comprobante")
            if comprobante_node is None or not comprobante_node.text:
                raise DocumentImportError("Missing XML payload inside autorizacion tag")
            xml_inner = comprobante_node.text.strip()
            inner_bytes = xml_inner.encode("utf-8")
            payload = self._ensure_payload(inner_bytes)
            payload.setdefault("access_key", self._value(root, "claveAcceso"))
            payload.setdefault("authorization", self._value(root, "numeroAutorizacion"))
            payload.setdefault(
                "authorization_date",
                self._parse_datetime(self._value(root, "fechaAutorizacion")),
            )
            return payload
        if tag in {"respuestaComprobante", "RespuestaAutorizacionComprobante"}:
            autorizaciones = root.find("autorizaciones")
            if autorizaciones is None:
                raise DocumentImportError("Authorization response without autorizaciones node")
            autorizacion = autorizaciones.find("autorizacion")
            if autorizacion is None:
                raise DocumentImportError("Authorization response without autorizacion entry")
            estado = self._value(autorizacion, "estado")
            if estado != "AUTORIZADO":
                raise DocumentImportError(
                    _("Document not authorized by SRI (state: %s)", estado or "-"),
                )
            return self._ensure_payload(etree.tostring(autorizacion))
        return {"root": root}

    def _tag(self, node):
        return node.tag.split("}")[-1]

    def _format_document_number(self, number):
        cleaned = re.sub(r"\D", "", number or "")
        if len(cleaned) == 15:
            return f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
        return number or ""

    def _value(self, node, xpath):
        found = node.find(xpath)
        if found is not None and found.text:
            return found.text.strip()
        return ""

    def _build_number(self, root):
        estab = self._value(root, "infoTributaria/estab").rjust(3, "0")
        pto_emi = self._value(root, "infoTributaria/ptoEmi").rjust(3, "0")
        secuencial = self._value(root, "infoTributaria/secuencial").rjust(9, "0")
        return f"{estab}-{pto_emi}-{secuencial}" if estab and pto_emi and secuencial else False

    def _parse_partner(self, root):
        return {
            "vat": self._value(root, "infoTributaria/ruc"),
            "name": self._value(root, "infoTributaria/razonSocial"),
        }

    def _date_node(self, doc_code):
        mapping = {
            "01": "infoFactura/fechaEmision",
            "03": "infoLiquidacionCompra/fechaEmision",
            "04": "infoNotaCredito/fechaEmision",
            "05": "infoNotaDebito/fechaEmision",
            "07": "infoCompRetencion/fechaEmision",
        }
        return mapping.get(doc_code, "infoFactura/fechaEmision")

    def _parse_date(self, value):
        if not value:
            return False
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise DocumentImportError(_("Unsupported date format: %s", value))

    def _parse_datetime(self, value):
        if not value:
            return False
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return False

    def _parse_lines(self, root, doc_code):
        lines = []
        detalle_nodes = root.findall("detalles/detalle")
        for detalle in detalle_nodes:
            taxes = []
            for tax in detalle.findall("impuestos/impuesto"):
                taxes.append(
                    {
                        "group_code": self._value(tax, "codigo"),
                        "code": self._value(tax, "codigoPorcentaje"),
                        "rate": self._float(self._value(tax, "tarifa")),
                        "base": self._float(self._value(tax, "baseImponible")),
                        "amount": self._float(self._value(tax, "valor")),
                    }
                )
            line = {
                "description": self._value(detalle, "descripcion"),
                "quantity": self._float(self._value(detalle, "cantidad"), default=1.0),
                "price_unit": self._float(self._value(detalle, "precioUnitario")),
                "discount": self._float(self._value(detalle, "descuento")),
                "subtotal": self._float(self._value(detalle, "precioTotalSinImpuesto")),
                "taxes": taxes,
            }
            lines.append(line)
        return lines

    def _parse_totals(self, root, doc_code):
        total_node = {
            "01": "infoFactura/importeTotal",
            "03": "infoLiquidacionCompra/importeTotal",
            "04": "infoNotaCredito/valorModificacion",
        }.get(doc_code, "infoFactura/importeTotal")
        subtotal_node = {
            "01": "infoFactura/totalSinImpuestos",
            "03": "infoLiquidacionCompra/totalSinImpuestos",
            "04": "infoNotaCredito/totalSinImpuestos",
        }.get(doc_code, "infoFactura/totalSinImpuestos")
        totals = {
            "total": self._float(self._value(root, total_node)),
            "subtotal": self._float(self._value(root, subtotal_node)),
            "taxes": [],
        }
        tax_container_xpath = {
            "01": "infoFactura/totalConImpuestos",
            "03": "infoLiquidacionCompra/totalConImpuestos",
            "04": "infoNotaCredito/totalConImpuestos",
        }.get(doc_code)
        if tax_container_xpath:
            for tax in root.findall(f"{tax_container_xpath}/totalImpuesto"):
                totals["taxes"].append(
                    {
                        "group_code": self._value(tax, "codigo"),
                        "code": self._value(tax, "codigoPorcentaje"),
                        "base": self._float(self._value(tax, "baseImponible")),
                        "amount": self._float(self._value(tax, "valor")),
                    }
                )
        return totals

    def _parse_references(self, root, doc_code):
        if doc_code == "04":
            return {
                "original_number": self._value(root, "infoNotaCredito/numDocModificado"),
                "original_date": self._parse_date(
                    self._value(root, "infoNotaCredito/fechaEmisionDocSustento"),
                )
                or False,
                "original_authorization": self._value(
                    root, "infoNotaCredito/numAutDocModificado"
                ),
                "reason": self._value(root, "infoNotaCredito/motivo"),
            }
        if doc_code == "05":
            motivos = root.findall("infoNotaDebito/motivos/motivo")
            reason = "\n".join(
                filter(None, (self._value(motivo, "motivo") for motivo in motivos))
            )
            return {
                "original_number": self._value(root, "infoNotaDebito/numDocModificado"),
                "original_date": self._parse_date(
                    self._value(root, "infoNotaDebito/fechaEmisionDocSustento"),
                )
                or False,
                "original_authorization": self._value(
                    root, "infoNotaDebito/numAutDocModificado"
                ),
                "reason": reason or False,
            }
        return {}

    def _parse_sustento(self, root, doc_code):
        sustento = []
        if doc_code != "07":
            return sustento
        for doc in root.findall("docsSustento/docSustento"):
            retentions = []
            for retention in doc.findall("retenciones/retencion"):
                retentions.append(
                    {
                        "group_code": self._value(retention, "codigo"),
                        "code": self._value(retention, "codigoRetencion"),
                        "base": self._float(self._value(retention, "baseImponible")),
                        "rate": self._float(self._value(retention, "porcentajeRetener")),
                        "amount": self._float(self._value(retention, "valorRetenido")),
                    }
                )
            sustento.append(
                {
                    "tax_support": self._value(doc, "codSustento"),
                    "support_code": self._value(doc, "codDocSustento"),
                    "support_number": self._format_document_number(self._value(doc, "numDocSustento")),
                    "support_number_raw": self._value(doc, "numDocSustento"),
                    "support_date": self._parse_date(self._value(doc, "fechaEmisionDocSustento")),
                    "total": self._float(self._value(doc, "importeTotal")),
                    "retentions": retentions,
                }
            )
        return sustento

    def _float(self, value, default=0.0):
        if value in (None, ""):
            return default
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            raise DocumentImportError(_("Invalid numeric value: %s", value))


class L10nEcEdiImportWizard(models.TransientModel):
    """Transient wizard to orchestrate an import execution."""

    _name = "l10n.ec.edi.import.wizard"
    _description = "Ecuador EDI Import Wizard"

    file_ids = fields.One2many(
        "l10n.ec.edi.import.wizard.file",
        "wizard_id",
        string="Files",
        required=True,
        copy=False,
    )
    create_missing_partners = fields.Boolean(
        string="Create Missing Partners",
        default=True,
        help="If enabled, a supplier will be created automatically when not found.",
    )
    allow_duplicate = fields.Boolean(
        string="Allow Duplicates",
        default=False,
        help="If disabled, documents already loaded in Odoo are skipped.",
    )
    validate_with_sri = fields.Boolean(
        string="Validate With SRI",
        default=True,
        help="Contact the SRI authorization service when access keys are provided.",
    )
    session_id = fields.Many2one(
        "account.edi.import.session",
        string="Session",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("done", "Summary"),
        ],
        default="draft",
    )
    summary_message = fields.Text(readonly=True)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_start_import(self):
        self.ensure_one()
        if not self.file_ids:
            raise UserError(_("Please attach at least one file to process."))

        session = self.env["account.edi.import.session"].create({"state": "draft"})
        session.mark_running()
        self.session_id = session

        start = time.perf_counter()
        try:
            counters = self._process_all_files(session)
            session.mark_done()
            self.summary_message = self._format_summary(counters)
            self.state = "done"
        except Exception as err:  # noqa: BLE001 - top level error capture for wizard
            _logger.exception("EDI import failed")
            session.mark_failed(str(err))
            raise
        finally:
            duration = time.perf_counter() - start
            _logger.info(
                "EDI import session %s completed in %.2fs", session.name, duration
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------
    def _process_all_files(self, session):
        parser = DocumentParser(self.env.company)
        counters = defaultdict(int)
        for line in self.file_ids:
            filename = line.filename or "attachment"
            raw = base64.b64decode(line.data or b"")
            ext = (filename.split(".")[-1]).lower() if "." in filename else ""
            if ext == "xml":
                counters = self._handle_xml_content(session, raw, filename, parser, counters)
            elif ext == "txt":
                counters = self._handle_txt_content(session, raw, filename, parser, counters)
            elif ext == "zip":
                counters = self._handle_zip_content(session, raw, parser, counters)
            else:
                raise UserError(
                    _("Unsupported file extension for %s. Only XML/TXT/ZIP are accepted.", filename)
                )
        return counters

    def _handle_xml_content(self, session, raw, filename, parser, counters):
        start = time.perf_counter()
        try:
            doc_info = parser.parse(raw)
            result = self._process_document(session, doc_info, raw)
        except DocumentImportError as parse_err:
            result = self._log_error(session, payload=raw, message=str(parse_err))
        except Exception as err:
            result = self._log_error(session, payload=raw, message=str(err))
        result["processing_time"] = time.perf_counter() - start
        self._create_log(session, result)
        counters[result["status"]] += 1
        return counters

    def _handle_txt_content(self, session, raw, filename, parser, counters):
        content = self._decode_bytes(raw)
        access_keys = self._extract_access_keys(content)
        if not access_keys:
            result = self._log_warning(
                session,
                message=_("No access keys found in %s", filename),
                payload=content,
            )
            self._create_log(session, result)
            counters[result["status"]] += 1
            return counters

        sri_client = self.env["l10n.ec.edi.import.sri.client"]
        for access_key in access_keys:
            start = time.perf_counter()
            try:
                xml_info = sri_client.fetch_document(self.env.company, access_key)
                if not xml_info["xml"]:
                    raise DocumentImportError(xml_info.get("message") or "SRI returned an empty payload")
                doc_info = parser.parse(xml_info["xml"].encode("utf-8"))
                doc_info.setdefault("authorization", xml_info.get("authorization"))
                doc_info.setdefault("authorization_date", xml_info.get("authorization_date"))
                doc_info.setdefault("access_key", access_key)
                result = self._process_document(session, doc_info, xml_info["xml"].encode("utf-8"))
            except DocumentImportError as parse_err:
                result = self._log_error(
                    session,
                    access_key=access_key,
                    message=str(parse_err),
                )
            except Exception as err:
                result = self._log_error(
                    session,
                    access_key=access_key,
                    message=str(err),
                )
            result["processing_time"] = time.perf_counter() - start
            result.setdefault("access_key", access_key)
            self._create_log(session, result)
            counters[result["status"]] += 1
            time.sleep(0.3)  # rate limiting for SRI
        return counters

    def _handle_zip_content(self, session, raw, parser, counters):
        import zipfile
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(raw)) as zipf:
            for member in zipf.namelist():
                if member.endswith("/"):
                    continue
                data = zipf.read(member)
                if member.lower().endswith(".xml"):
                    counters = self._handle_xml_content(session, data, member, parser, counters)
                elif member.lower().endswith(".txt"):
                    counters = self._handle_txt_content(session, data, member, parser, counters)
                else:
                    _logger.info("Ignoring unsupported file %s inside archive", member)
        return counters

    # ------------------------------------------------------------------
    # Document handling
    # ------------------------------------------------------------------
    def _process_document(self, session, doc_info, raw_payload):
        mapping = SUPPORTED_DOC_TYPES.get(doc_info.get("document_code"))
        if not mapping:
            return self._log_error(
                session,
                message=_("Document type %s is not supported", doc_info.get("document_code")),
                payload=raw_payload,
                document_number=doc_info.get("document_number"),
                access_key=doc_info.get("access_key"),
            )

        partner = self._get_partner(doc_info)
        duplicate = self._find_duplicate(mapping, partner, doc_info)
        if duplicate and not self.allow_duplicate:
            return {
                "status": "skipped",
                "document_code": doc_info.get("document_code"),
                "document_type": mapping["label"],
                "document_number": doc_info.get("document_number"),
                "access_key": doc_info.get("access_key"),
                "issue_date": doc_info.get("issue_date"),
                "partner_id": partner.id if partner else False,
                "partner_vat": partner.vat if partner else False,
                "amount_total": doc_info.get("totals", {}).get("total"),
                "message": _("Document already imported as %s", duplicate.display_name),
                "payload": raw_payload.decode("utf-8", errors="ignore"),
                "target_model": duplicate._name,
                "target_res_id": duplicate.id,
            }

        amount_total = doc_info.get("totals", {}).get("total")
        if mapping["internal_type"] == "withhold":
            record, amount_total = self._create_withhold(partner, doc_info, mapping)
        elif mapping["internal_type"] == "credit_note":
            record = self._create_credit_note(partner, doc_info, mapping)
        else:
            record = self._create_vendor_bill(partner, doc_info, mapping)

        if not record:
            return self._log_error(
                session,
                message=_("No document was created for %s", doc_info.get("document_number")),
                payload=raw_payload,
                document_number=doc_info.get("document_number"),
                access_key=doc_info.get("access_key"),
            )

        return {
            "status": "success",
            "document_code": doc_info.get("document_code"),
            "document_type": mapping["label"],
            "document_number": doc_info.get("document_number"),
            "access_key": doc_info.get("access_key"),
            "issue_date": doc_info.get("issue_date"),
            "partner_id": partner.id if partner else False,
            "partner_vat": partner.vat if partner else False,
            "amount_total": amount_total,
            "payload": raw_payload.decode("utf-8", errors="ignore"),
            "target_model": record._name,
            "target_res_id": record.id,
        }

    def _create_vendor_bill(self, partner, doc_info, mapping):
        company = self.env.company
        journal = self._find_purchase_journal(mapping["internal_type"], company)
        move_vals = self._prepare_move_vals(partner, doc_info, mapping, journal)
        move_vals["invoice_line_ids"] = self._prepare_invoice_lines(doc_info, company)
        move = self.env["account.move"].with_company(company).create(move_vals)
        return move

    def _create_credit_note(self, partner, doc_info, mapping):
        company = self.env.company
        journal = self._find_purchase_journal(mapping["internal_type"], company)
        move_vals = self._prepare_move_vals(partner, doc_info, mapping, journal)
        references = doc_info.get("references", {}) or {}
        self._apply_legacy_fields(move_vals, mapping, references)
        move_vals["invoice_line_ids"] = self._prepare_invoice_lines(
            doc_info, company, is_refund=True
        )
        return self.env["account.move"].with_company(company).create(move_vals)

    def _create_withhold(self, partner, doc_info, mapping):
        company = self.env.company
        journal = self._find_withhold_journal(company)
        line_commands, invoices, total_amount = self._prepare_withhold_lines(company, partner, doc_info)
        latam_type = self.env.ref(mapping["latam_xml_id"], raise_if_not_found=False)
        move_vals = {
            "move_type": mapping["move_type"],
            "partner_id": partner.id if partner else False,
            "company_id": company.id,
            "journal_id": journal.id,
            "date": doc_info.get("issue_date"),
            "l10n_latam_document_number": doc_info.get("document_number"),
            "ref": doc_info.get("document_number"),
            "l10n_ec_electronic_authorization": doc_info.get("authorization"),
            "l10n_ec_withholding_type": "purchase",
            "invoice_origin": doc_info.get("access_key"),
            "currency_id": company.currency_id.id,
            "line_ids": line_commands,
        }
        if latam_type:
            move_vals["l10n_latam_document_type_id"] = latam_type.id
        move = self.env["account.move"].with_company(company).create(move_vals)
        move._post()

        if invoices:
            invoices.write({"l10n_ec_withhold_ids": [(4, move.id)]})
            self._reconcile_withholding_move(move, invoices)
        move.line_ids.filtered(lambda line: line.tax_ids).write({"l10n_ec_withhold_id": move.id})
        return move, total_amount

    # ------------------------------------------------------------------
    # Record preparation
    # ------------------------------------------------------------------
    def _prepare_move_vals(self, partner, doc_info, mapping, journal):
        latam_type = self.env.ref(mapping["latam_xml_id"], raise_if_not_found=False)
        vals = {
            "move_type": mapping["move_type"],
            "partner_id": partner.id if partner else False,
            "company_id": self.env.company.id,
            "invoice_date": doc_info.get("issue_date"),
            "date": doc_info.get("issue_date"),
            "l10n_latam_document_number": doc_info.get("document_number"),
            "l10n_ec_electronic_authorization": doc_info.get("authorization"),
            "journal_id": journal.id,
            "currency_id": self.env.company.currency_id.id,
            "invoice_origin": doc_info.get("access_key"),
        }
        if latam_type:
            vals["l10n_latam_document_type_id"] = latam_type.id
        return vals

    def _apply_legacy_fields(self, move_vals, mapping, references):
        internal_type = mapping.get("internal_type")
        if internal_type not in {"credit_note", "debit_note"}:
            return
        move_vals["l10n_latam_internal_type"] = internal_type
        legacy_number = self._normalize_document_number(
            references.get("original_number") or ""
        )
        move_vals["l10n_ec_legacy_document_number"] = legacy_number or False
        move_vals["l10n_ec_legacy_document_date"] = references.get("original_date") or False
        move_vals["l10n_ec_legacy_document_authorization"] = references.get("original_authorization") or False
        move_vals["l10n_ec_reason"] = references.get("reason") or False

    def _normalize_document_number(self, number):
        if not number:
            return ""
        cleaned = re.sub(r"\D", "", number)
        if len(cleaned) == 15:
            return f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
        return number

    def _prepare_invoice_lines(self, doc_info, company, is_refund=False):
        line_vals = []
        for line in doc_info.get("lines", []):
            taxes = self._map_taxes(company, line.get("taxes", []))
            quantity = line.get("quantity", 1.0)
            price_unit = line.get("price_unit", 0.0)
            if is_refund:
                price_unit = -abs(price_unit)
                quantity = abs(quantity)
            vals = {
                "name": line.get("description") or "/",
                "quantity": quantity,
                "price_unit": price_unit,
                "discount": line.get("discount", 0.0),
                "tax_ids": [(6, 0, taxes.ids)],
            }
            if not taxes:
                vals["tax_ids"] = [(5, 0, 0)]
            line_vals.append((0, 0, vals))
        if not line_vals:
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "name": doc_info.get("document_number") or "Import line",
                        "quantity": 1.0,
                        "price_unit": doc_info.get("totals", {}).get("subtotal", 0.0),
                    },
                )
            )
        return line_vals

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def _find_purchase_journal(self, internal_type, company):
        domain = [
            ("company_id", "=", company.id),
        ]
        if internal_type == "purchase_liquidation":
            domain += [("l10n_ec_is_purchase_liquidation", "=", True)]
        else:
            domain += [("type", "=", "purchase")]
        journal = self.env["account.journal"].search(domain, limit=1)
        if not journal:
            raise DocumentImportError(
                _("No purchase journal configured for company %s", company.display_name)
            )
        return journal

    def _find_withhold_journal(self, company):
        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", company.id),
                ("l10n_ec_withholding_type", "=", "purchase"),
            ],
            limit=1,
        )
        if not journal:
            raise DocumentImportError(
                _("No purchase withholding journal configured for company %s", company.display_name)
            )
        return journal

    def _get_partner(self, doc_info):
        data = doc_info.get("partner", {})
        vat = data.get("vat")
        name = data.get("name")
        if not vat:
            raise DocumentImportError(_("Supplier VAT is missing in the document."))
        partner = self.env["res.partner"].search(
            [
                ("vat", "=", vat),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            limit=1,
        )
        if partner:
            return partner
        if not self.create_missing_partners:
            raise DocumentImportError(
                _("Supplier with VAT %s not found and auto-creation disabled.", vat)
            )
        country = self.env.ref("base.ec", raise_if_not_found=False)
        partner = self.env["res.partner"].create(
            {
                "name": name or vat,
                "vat": vat,
                "company_type": "company",
                "country_id": country.id if country else False,
                "supplier_rank": 1,
                "company_id": self.env.company.id,
            }
        )
        return partner

    def _find_duplicate(self, mapping, partner, doc_info):
        domain = [
            ("company_id", "=", self.env.company.id),
            ("move_type", "=", mapping["move_type"]),
            ("l10n_latam_document_number", "=", doc_info.get("document_number")),
        ]
        if partner:
            domain.append(("partner_id", "=", partner.id))
        existing = self.env["account.move"].search(domain, limit=1)
        return existing

    def _find_vendor_document(self, partner, number, company, support_doc_type=None):
        domain = [
            ("company_id", "=", company.id),
            ("partner_id", "=", partner.id if partner else False),
        ]
        if support_doc_type == "04":
            domain.append(("move_type", "=", "in_refund"))
        else:
            domain.append(("move_type", "in", ["in_invoice", "in_refund"]))

        candidates = set()
        if number:
            candidates.add(number)
            number_plain = re.sub(r"\D", "", number)
            if number_plain:
                candidates.add(number_plain)
        doc_domains = []
        for candidate in candidates:
            variants = {candidate}
            plain_number = re.sub(r"\D", "", candidate or "")
            if plain_number:
                variants.add(plain_number)
            formatted_number = self._normalize_document_number(candidate)
            if formatted_number:
                variants.add(formatted_number)
            for variant in variants:
                doc_domains.append([( "l10n_latam_document_number", "=", variant)])
                doc_domains.append([( "l10n_ec_legacy_document_number", "=", variant)])
        if not doc_domains:
            return self.env["account.move"].search(domain, limit=1)

        document_domain = doc_domains.pop()
        while doc_domains:
            document_domain = expression.OR([document_domain, doc_domains.pop()])
        search_domain = expression.AND([domain, document_domain])
        return self.env["account.move"].search(search_domain, limit=1)

    def _map_taxes(self, company, taxes_data):
        mapped = self.env["account.tax"]
        for tax in taxes_data:
            domain = [
                ("company_id", "=", company.id),
                ("type_tax_use", "!=", "sale"),
                ("l10n_ec_xml_fe_code", "=", tax.get("code")),
                ("tax_group_id.l10n_ec_xml_fe_code", "=", tax.get("group_code")),
            ]
            result = self.env["account.tax"].search(domain, limit=1)
            if result:
                mapped |= result
        return mapped

    def _prepare_withhold_lines(self, company, partner, doc_info):
        currency = company.currency_id
        lines = []
        invoices = self.env["account.move"]
        totals_by_invoice = defaultdict(float)
        supports = doc_info.get("sustento") or []
        if not supports:
            raise DocumentImportError(_("Withholding document does not contain support information."))
        for support in supports:
            support_number = support.get("support_number") or support.get("support_number_raw")
            invoice = self._find_vendor_document(
                partner,
                support.get("support_number") or support.get("support_number_raw"),
                company,
                support.get("support_code"),
            )
            if not invoice:
                raise DocumentImportError(
                    _(
                        "Referenced document %s not found for withholding %s",
                        support_number or "-",
                        doc_info.get("document_number") or "-",
                    )
                )
            invoices |= invoice
            tax_support = support.get("tax_support") or invoice.l10n_ec_tax_support
            for retention in support.get("retentions", []) or []:
                tax = self._map_withhold_tax(company, retention)
                if not tax:
                    raise DocumentImportError(
                        _(
                            "Unable to map withholding code %(code)s (group %(group)s) for document %(document)s",
                            code=retention.get("code"),
                            group=retention.get("group_code"),
                            document=support_number or "-",
                        )
                    )
                line_pair, withheld_amount = self._build_withhold_line_vals(
                    company,
                    tax,
                    retention,
                    invoice,
                    doc_info,
                    tax_support,
                    partner,
                )
                if line_pair:
                    lines.extend(line_pair)
                    totals_by_invoice[invoice] += withheld_amount
        if not lines:
            raise DocumentImportError(_("No withholding lines could be generated for this document."))

        if partner and not partner.property_account_payable_id:
            raise DocumentImportError(
                _("Vendor %s is missing a payable account.", partner.display_name)
            )

        for invoice, total in list(totals_by_invoice.items()):
            total = currency.round(total)
            if not total:
                continue
            move_name = _(
                "RET: %(document)s Invoice: %(invoice)s",
                document=doc_info.get("document_number") or "",
                invoice=invoice.l10n_latam_document_number or invoice.name,
            )
            lines.append(
                (
                    0,
                    0,
                    {
                        "partner_id": partner.id if partner else False,
                        "account_id": partner.property_account_payable_id.id,
                        "l10n_ec_invoice_withhold_id": invoice.id,
                        "name": move_name,
                        "debit": total,
                        "credit": 0.0,
                    },
                )
            )

        total_amount = currency.round(sum(totals_by_invoice.values()))
        return lines, invoices, total_amount

    def _map_withhold_tax(self, company, retention):
        retention_code = (retention.get("code") or "").strip()
        group_code = (retention.get("group_code") or "").strip()
        domain = [("company_id", "=", company.id)]
        if group_code == "1":
            domain += [
                ("tax_group_id.l10n_ec_type", "=", "withhold_income_purchase"),
                ("l10n_ec_code_base", "=", retention_code),
            ]
        elif group_code == "2":
            domain += [
                ("tax_group_id.l10n_ec_type", "=", "withhold_vat_purchase"),
                ("l10n_ec_xml_fe_code", "=", retention_code),
            ]
        else:
            return self.env["account.tax"]
        return self.env["account.tax"].with_company(company).search(domain, limit=1)

    def _build_withhold_line_vals(self, company, tax, retention, invoice, doc_info, tax_support, partner):
        currency = company.currency_id
        base_amount = retention.get("base")
        if not base_amount:
            return [], 0.0
        is_refund = invoice.move_type in ("out_refund", "in_refund")
        taxes_data = tax.with_company(company).compute_all(
            base_amount,
            currency=currency,
            quantity=1.0,
            partner=partner,
            is_refund=is_refund,
        )
        line_commands = []
        withheld_total = 0.0
        reference = doc_info.get("document_number") or invoice.l10n_latam_document_number or invoice.name
        is_inbound = invoice.is_inbound()
        for tax_line in taxes_data.get("taxes", []):
            account_id = tax_line.get("account_id") or tax_line.get("refund_account_id")
            if not account_id:
                raise DocumentImportError(
                    _(
                        "Withholding tax %(tax)s is missing an account for company %(company)s",
                        tax=tax.display_name,
                        company=company.display_name,
                    )
                )
            base_value = abs(tax_line.get("base", 0.0))
            if not base_value:
                continue
            amount_value = abs(tax_line.get("amount", 0.0))
            if not amount_value:
                continue
            base_line = {
                "partner_id": partner.id if partner else False,
                "name": _("RET %s") % reference,
                "quantity": 1.0,
                "price_unit": base_value,
                "account_id": account_id,
                "tax_ids": [(6, 0, tax.ids)],
                "display_type": "product",
                "l10n_ec_invoice_withhold_id": invoice.id,
                "l10n_ec_tax_support": tax_support,
                "debit": base_value if is_inbound else 0.0,
                "credit": 0.0 if is_inbound else base_value,
            }
            counterpart_line = {
                "partner_id": partner.id if partner else False,
                "name": _("Counterpart RET %s") % reference,
                "quantity": 1.0,
                "price_unit": base_value,
                "account_id": account_id,
                "tax_ids": [],
                "tax_tag_ids": [],
                "l10n_ec_invoice_withhold_id": invoice.id,
                "debit": 0.0 if is_inbound else base_value,
                "credit": base_value if is_inbound else 0.0,
            }
            line_commands.append((0, 0, base_line))
            line_commands.append((0, 0, counterpart_line))
            withheld_total += amount_value
        return line_commands, withheld_total

    def _reconcile_withholding_move(self, withhold_move, invoices):
        payable_type = "liability_payable"
        for invoice in invoices:
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == payable_type
            )
            withhold_lines = withhold_move.line_ids.filtered(
                lambda line: line.account_id.account_type == payable_type
                and line.l10n_ec_invoice_withhold_id == invoice
            )
            (invoice_lines + withhold_lines).reconcile()
        return True

    # ------------------------------------------------------------------
    # Logging utilities
    # ------------------------------------------------------------------
    def _create_log(self, session, data):
        self.env["account.edi.import.log"].create_from_result(session, data)

    def _log_error(self, session, message, payload=None, access_key=None, document_number=None):
        return {
            "status": "error",
            "message": message,
            "payload": payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else payload,
            "access_key": access_key,
            "document_number": document_number,
        }

    def _log_warning(self, session, message, payload=None):
        return {
            "status": "warning",
            "message": message,
            "payload": payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else payload,
        }

    # ------------------------------------------------------------------
    # Low level utilities
    # ------------------------------------------------------------------
    def _decode_bytes(self, raw):
        for encoding in ("utf-8", "latin-1", "windows-1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _extract_access_keys(self, content):
        keys = set(re.findall(r"\b\d{49}\b", content))
        return sorted(keys)

    def _format_summary(self, counters):
        lines = [_("Processed documents:" )]
        for status in ("success", "warning", "error", "skipped"):
            lines.append(f" - {status.title()}: {counters.get(status, 0)}")
        return "\n".join(lines)


class L10nEcEdiImportWizardFile(models.TransientModel):
    _name = "l10n.ec.edi.import.wizard.file"
    _description = "EDI Import Wizard File"

    wizard_id = fields.Many2one(
        "l10n.ec.edi.import.wizard",
        required=True,
        ondelete="cascade",
    )
    filename = fields.Char(required=True)
    data = fields.Binary(required=True)
