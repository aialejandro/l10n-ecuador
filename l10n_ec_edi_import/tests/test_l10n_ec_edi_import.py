# -*- coding: utf-8 -*-
import base64
from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase  # type: ignore[import]


INVOICE_XML = """
<factura>
    <infoTributaria>
        <ambiente>1</ambiente>
        <razonSocial>Proveedor Demo</razonSocial>
        <ruc>1790012345001</ruc>
        <claveAcceso>1234567890123456789012345678901234567890123456789</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>002</ptoEmi>
        <secuencial>000000123</secuencial>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>01/09/2025</fechaEmision>
        <totalSinImpuestos>100.00</totalSinImpuestos>
        <importeTotal>112.00</importeTotal>
        <moneda>USD</moneda>
        <totalConImpuestos>
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>2</codigoPorcentaje>
                <baseImponible>100.00</baseImponible>
                <valor>12.00</valor>
            </totalImpuesto>
        </totalConImpuestos>
    </infoFactura>
    <detalles>
        <detalle>
            <descripcion>Servicio de consultoría</descripcion>
            <cantidad>1.00</cantidad>
            <precioUnitario>100.00</precioUnitario>
            <descuento>0.00</descuento>
            <precioTotalSinImpuesto>100.00</precioTotalSinImpuesto>
            <impuestos>
                <impuesto>
                    <codigo>2</codigo>
                    <codigoPorcentaje>2</codigoPorcentaje>
                    <tarifa>12.0</tarifa>
                    <baseImponible>100.00</baseImponible>
                    <valor>12.00</valor>
                </impuesto>
            </impuestos>
        </detalle>
    </detalles>
</factura>
""".strip()

WITHHOLD_XML_TEMPLATE = """
<autorizacion>
    <estado>AUTORIZADO</estado>
    <numeroAutorizacion>2204202507099000419600120010640006191550001268514</numeroAutorizacion>
    <fechaAutorizacion>2025-04-22T16:35:20-05:00</fechaAutorizacion>
    <comprobante><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<comprobanteRetencion id="comprobante" version="2.0.0">
    <infoTributaria>
        <ambiente>2</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>CORPORACION DEMO SA</razonSocial>
        <nombreComercial>CORPORACION DEMO SA</nombreComercial>
        <ruc>0990004196001</ruc>
        <claveAcceso>2204202507099000419600120010640006191550001268514</claveAcceso>
        <codDoc>07</codDoc>
        <estab>001</estab>
        <ptoEmi>064</ptoEmi>
        <secuencial>000619155</secuencial>
        <dirMatriz>Av Principal 123</dirMatriz>
    </infoTributaria>
    <infoCompRetencion>
        <fechaEmision>%(date)s</fechaEmision>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <tipoIdentificacionSujetoRetenido>04</tipoIdentificacionSujetoRetenido>
        <razonSocialSujetoRetenido>Your Company</razonSocialSujetoRetenido>
        <identificacionSujetoRetenido>1790012345001</identificacionSujetoRetenido>
        <periodoFiscal>%(period)s</periodoFiscal>
    </infoCompRetencion>
    <docsSustento>
        <docSustento>
            <codSustento>01</codSustento>
            <codDocSustento>01</codDocSustento>
            <numDocSustento>%(invoice_number)s</numDocSustento>
            <fechaEmisionDocSustento>%(invoice_date)s</fechaEmisionDocSustento>
            <pagoLocExt>01</pagoLocExt>
            <totalSinImpuestos>27.22</totalSinImpuestos>
            <importeTotal>31.30</importeTotal>
            <impuestosDocSustento>
                <impuestoDocSustento>
                    <codImpuestoDocSustento>2</codImpuestoDocSustento>
                    <codigoPorcentaje>4</codigoPorcentaje>
                    <baseImponible>27.22</baseImponible>
                    <tarifa>15</tarifa>
                    <valorImpuesto>4.08</valorImpuesto>
                </impuestoDocSustento>
            </impuestosDocSustento>
            <retenciones>
                <retencion>
                    <codigo>2</codigo>
                    <codigoRetencion>10</codigoRetencion>
                    <baseImponible>4.08</baseImponible>
                    <porcentajeRetener>20.00</porcentajeRetener>
                    <valorRetenido>0.82</valorRetenido>
                </retencion>
                <retencion>
                    <codigo>1</codigo>
                    <codigoRetencion>3440</codigoRetencion>
                    <baseImponible>27.22</baseImponible>
                    <porcentajeRetener>2.75</porcentajeRetener>
                    <valorRetenido>0.75</valorRetenido>
                </retencion>
            </retenciones>
            <pagos>
                <pago>
                    <formaPago>01</formaPago>
                    <total>31.30</total>
                </pago>
            </pagos>
        </docSustento>
    </docsSustento>
</comprobanteRetencion>]]></comprobante>
</autorizacion>
""".strip()


class TestL10nEcEdiImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["l10n.ec.edi.import.wizard"]
        cls.Move = cls.env["account.move"]
        cls.company = cls.env.company
        country = cls.env.ref("base.ec")
        cls.company.write(
            {
                "account_fiscal_country_id": country.id,
                "currency_id": cls.env.ref("base.USD").id,
            }
        )
        cls.company.partner_id.write({"country_id": country.id, "vat": "1790012345001"})

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Proveedor Demo",
                "vat": "0990004196001",
                "company_type": "company",
                "country_id": country.id,
                "company_id": cls.company.id,
            }
        )

        cls.expense_account = cls.env["account.account"].create(
            {
                "name": "Gastos Servicios",
                "code": "SERV123",
                "account_type": "expense",
                "company_id": cls.company.id,
            }
        )
        cls.withhold_vat_account = cls.env["account.account"].create(
            {
                "name": "Ret IVA",
                "code": "RETIVA",
                "account_type": "liability_current",
                "company_id": cls.company.id,
            }
        )
        cls.withhold_profit_account = cls.env["account.account"].create(
            {
                "name": "Ret Renta",
                "code": "RETRENTA",
                "account_type": "liability_current",
                "company_id": cls.company.id,
            }
        )

        vat_group = cls.env["account.tax.group"].create(
            {
                "name": "Ret IVA Compras",
                "l10n_ec_type": "withhold_vat_purchase",
                "l10n_ec_xml_fe_code": "2",
            }
        )
        profit_group = cls.env["account.tax.group"].create(
            {
                "name": "Ret Renta Compras",
                "l10n_ec_type": "withhold_income_purchase",
                "l10n_ec_xml_fe_code": "1",
            }
        )

        cls.tax_withhold_vat_20 = cls.env["account.tax"].create(
            {
                "name": "Ret IVA 20%",
                "type_tax_use": "purchase",
                "amount_type": "percent",
                "amount": -20.0,
                "company_id": cls.company.id,
                "tax_group_id": vat_group.id,
                "l10n_ec_xml_fe_code": "10",
                "invoice_repartition_line_ids": [
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        }
                    ),
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.withhold_vat_account.id,
                        }
                    ),
                ],
                "refund_repartition_line_ids": [
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        }
                    ),
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.withhold_vat_account.id,
                        }
                    ),
                ],
            }
        )
        cls.tax_withhold_profit_3440 = cls.env["account.tax"].create(
            {
                "name": "Ret Renta 2.75%",
                "type_tax_use": "purchase",
                "amount_type": "percent",
                "amount": -2.75,
                "company_id": cls.company.id,
                "tax_group_id": profit_group.id,
                "l10n_ec_code_base": "3440",
                "invoice_repartition_line_ids": [
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        }
                    ),
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.withhold_profit_account.id,
                        }
                    ),
                ],
                "refund_repartition_line_ids": [
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        }
                    ),
                    Command.create(
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.withhold_profit_account.id,
                        }
                    ),
                ],
            }
        )

        cls.withhold_journal = cls.env["account.journal"].create(
            {
                "name": "Retenciones Compras",
                "code": "RET",
                "type": "general",
                "company_id": cls.company.id,
                "l10n_ec_withholding_type": "purchase",
            }
        )

        purchase_journal = cls.env["account.journal"].search(
            [
                ("company_id", "=", cls.company.id),
                ("type", "=", "purchase"),
            ],
            limit=1,
        )
        if not purchase_journal:
            purchase_journal = cls.env["account.journal"].create(
                {
                    "name": "Compras",
                    "code": "COMP",
                    "type": "purchase",
                    "company_id": cls.company.id,
                }
            )

        cls.invoice = cls.Move.with_company(cls.company).create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.partner.id,
                "journal_id": purchase_journal.id,
                "invoice_date": date(2025, 4, 11),
                "l10n_latam_document_type_id": cls.env.ref("l10n_ec.ec_dt_01").id,
                "l10n_latam_document_number": "001-050-000005614",
                "l10n_ec_legacy_document_number": "001-050-000005614",
                "l10n_ec_electronic_authorization": "1234567890",
                "l10n_ec_tax_support": "01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Servicios",
                            "account_id": cls.expense_account.id,
                            "price_unit": 27.22,
                            "quantity": 1.0,
                        },
                    )
                ],
            }
        )
        cls.invoice.action_post()

    def _create_wizard(self, xml_payload, allow_duplicate=False):
        return self.Wizard.create(
            {
                "allow_duplicate": allow_duplicate,
                "file_ids": [
                    (
                        0,
                        0,
                        {
                            "filename": "invoice.xml",
                            "data": base64.b64encode(xml_payload.encode("utf-8")),
                        },
                    )
                ],
            }
        )

    def test_import_invoice_creates_vendor_bill(self):
        wizard = self._create_wizard(INVOICE_XML)
        wizard.action_start_import()

        self.assertEqual(wizard.state, "done")
        session = wizard.session_id
        self.assertEqual(session.success_count, 1)
        self.assertEqual(session.error_count, 0)

        log = session.log_ids
        self.assertEqual(log.status, "success")
        self.assertTrue(log.target_model)
        move = self.Move.browse(log.target_res_id)
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.l10n_latam_document_number, "001-002-000000123")
        self.assertEqual(move.invoice_origin, "1234567890123456789012345678901234567890123456789")

    def test_import_invoice_duplicate_skipped(self):
        wizard = self._create_wizard(INVOICE_XML)
        wizard.action_start_import()

        duplicate_wizard = self._create_wizard(INVOICE_XML)
        duplicate_wizard.action_start_import()

        self.assertEqual(duplicate_wizard.session_id.skipped_count, 1)
        log = duplicate_wizard.session_id.log_ids
        self.assertEqual(log.status, "skipped")

    def _create_withhold_wizard(self, xml_payload):
        return self.Wizard.create(
            {
                "file_ids": [
                    (
                        0,
                        0,
                        {
                            "filename": "withhold.xml",
                            "data": base64.b64encode(xml_payload.encode("utf-8")),
                        },
                    )
                ],
            }
        )

    def test_import_withholding_creates_move(self):
        withhold_xml = WITHHOLD_XML_TEMPLATE % {
            "date": "22/04/2025",
            "period": "04/2025",
            "invoice_number": "001050000005614",
            "invoice_date": "11/04/2025",
        }
        wizard = self._create_withhold_wizard(withhold_xml)
        wizard.action_start_import()

        session = wizard.session_id
        self.assertEqual(session.success_count, 1)
        log = session.log_ids
        self.assertEqual(log.status, "success")
        move = self.Move.browse(log.target_res_id)
        self.assertEqual(move.l10n_ec_withholding_type, "purchase")
        self.assertEqual(move.l10n_latam_document_number, "001-064-000619155")
        self.assertEqual(move.partner_id, self.partner)
        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(log.amount_total, 1.57, places=2)
        self.assertTrue(self.invoice in move.line_ids.mapped("l10n_ec_invoice_withhold_id"))
        self.assertEqual(move.amount_total, 0.0)
        payable_line = move.line_ids.filtered(
            lambda line: line.account_id == self.partner.property_account_payable_id
        )
        self.assertEqual(len(payable_line), 1)
        self.assertAlmostEqual(payable_line.debit, 1.57, places=2)
        self.assertIn(move, self.invoice.l10n_ec_withhold_ids)
        self.assertEqual(self.invoice.payment_state, "partial")
