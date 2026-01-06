from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_ec_report_line_name = fields.Char(
        string="EC Report Line Description",
        help="Description used in Ecuadorian EDI invoice reports.",
        copy=False,
    )

    def _l10n_ec_should_use_report_line_name(self):
        self.ensure_one()
        if not self.move_id or self.move_id.company_id.account_fiscal_country_id.code != 'EC':
            return False
        if self.move_id.move_type != 'out_invoice':
            return False
        if not (
            self.company_id.l10n_ec_hide_invoice_line_product_code
            or self.company_id.l10n_ec_hide_invoice_line_product_name
        ):
            return False
        return self.display_type == 'product' and bool(self.product_id)

    def _l10n_ec_prepare_report_line_name(self):
        """Prepare the text to print for this line in Ecuadorian customer invoice reports.

        Goal: hide product code and/or product name only in the printed report, while keeping
        any user-entered extra description lines (e.g. sale line description) untouched.
        """
        self.ensure_one()
        if self.display_type != 'product' or not self.product_id:
            return False
        if self.move_id.move_type != 'out_invoice':
            return False

        hide_code = bool(self.company_id.l10n_ec_hide_invoice_line_product_code)
        hide_name = bool(self.company_id.l10n_ec_hide_invoice_line_product_name)

        product = self.product_id.with_context(lang=self.partner_id.lang) if self.partner_id.lang else self.product_id

        header_with_code = product.display_name
        header_no_code = product.with_context(display_default_code=False).display_name
        header_code_only = product.default_code or ''

        name_text = self.name or ''
        name_lines = name_text.split('\n') if name_text else []

        # Keep whatever is after the product header line (user-entered extra description).
        if name_lines and name_lines[0] in {header_with_code, header_no_code, header_code_only}:
            tail_lines = name_lines[1:]
        else:
            # Not a recognizable auto-generated header, treat whole label as user content.
            return name_text

        # Avoid leading blank line when we remove the header.
        while tail_lines and tail_lines[0] == '':
            tail_lines.pop(0)

        if hide_code and hide_name:
            out_lines = tail_lines
        elif hide_code and not hide_name:
            out_lines = [header_no_code] + tail_lines
        elif hide_name and not hide_code:
            out_lines = ([header_code_only] if header_code_only else []) + tail_lines
        else:
            out_lines = [header_with_code] + tail_lines

        return '\n'.join(out_lines)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.l10n_ec_report_line_name is False and line._l10n_ec_should_use_report_line_name():
                line.l10n_ec_report_line_name = line._l10n_ec_prepare_report_line_name()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'product_id', 'name', 'display_type', 'move_id'} & set(vals):
            for line in self:
                if line._l10n_ec_should_use_report_line_name():
                    line.l10n_ec_report_line_name = line._l10n_ec_prepare_report_line_name()
        return res

    def l10n_ec_get_invoice_edi_data(self, taxes_data):
        self.ensure_one()
        EdiDocument = self.env["account.edi.document"]
        edi_values = self._prepare_edi_vals_to_export()
        res = {
            "codigoPrincipal": EdiDocument._l10n_ec_clean_str(
                self.product_id.default_code or "NA"
            )[:25],
            "codigoAuxiliar": False,
            "descripcion": EdiDocument._l10n_ec_clean_str(
                (self.product_id.name or self.name or "NA")[:300]
            ),
            "unidadMedida": EdiDocument._l10n_ec_clean_str(
                (self.product_uom_id.display_name or "NA")[:50]
            ),
            "cantidad": EdiDocument._l10n_ec_number_format(self.quantity, decimals=6),
            "precioUnitario": EdiDocument._l10n_ec_number_format(
                self.price_unit, decimals=6
            ),
            "descuento": EdiDocument._l10n_ec_number_format(
                edi_values["price_discount"], decimals=6
            ),
            "precioTotalSinImpuesto": EdiDocument._l10n_ec_number_format(
                edi_values["price_subtotal_before_discount"], decimals=6
            ),
            "detallesAdicionales": self._l10n_ec_get_invoice_edi_additional_data(),
            "impuestos": self._l10n_ec_get_invoice_edi_taxes(taxes_data),
        }
        return res

    def l10n_ec_get_credit_note_edi_data(self, taxes_data):
        self.ensure_one()
        EdiDocument = self.env["account.edi.document"]
        edi_values = self._prepare_edi_vals_to_export()
        res = {
            "codigoInterno": EdiDocument._l10n_ec_clean_str(
                self.product_id.default_code or "NA"
            )[:25],
            "codigoAuxiliar": False,
            "descripcion": EdiDocument._l10n_ec_clean_str(
                (self.product_id.name or self.name or "NA")[:300]
            ),
            "cantidad": EdiDocument._l10n_ec_number_format(self.quantity, decimals=6),
            "precioUnitario": EdiDocument._l10n_ec_number_format(
                self.price_unit, decimals=6
            ),
            "descuento": EdiDocument._l10n_ec_number_format(
                edi_values["price_discount"], decimals=6
            ),
            "precioTotalSinImpuesto": EdiDocument._l10n_ec_number_format(
                edi_values["price_subtotal_before_discount"], decimals=6
            ),
            "detallesAdicionales": self._l10n_ec_get_credit_note_edi_additional_data(),
            "impuestos": self._l10n_ec_get_credit_note_edi_taxes(taxes_data),
        }
        return res

    def _l10n_ec_get_invoice_edi_additional_data(self):
        res = []
        return res

    def _l10n_ec_get_credit_note_edi_additional_data(self):
        res = []
        return res

    def _l10n_ec_get_invoice_edi_taxes(self, taxes_data):
        tax_values = []
        EdiDocument = self.env["account.edi.document"]
        
        if not taxes_data:
            return tax_values
            
        # En Odoo 18.0, usar la nueva estructura de datos
        tax_details = taxes_data.get("tax_details", {})
        
        # Iterar sobre todos los grupos de impuestos 
        for grouping_key, values in tax_details.items():
            # Si el grouping_key es un impuesto (objeto account.tax)
            if hasattr(grouping_key, 'tax_group_id') and hasattr(grouping_key, 'l10n_ec_xml_fe_code'):
                tax_data = {
                    "tax": grouping_key,
                    "base_amount_currency": values.get("base_amount_currency", 0.0),
                    "tax_amount_currency": values.get("tax_amount_currency", 0.0),
                }
                tax_values.append(EdiDocument._l10n_ec_prepare_tax_vals_edi(tax_data))
            
            # Si hay group_tax_details, procesarlos
            elif "group_tax_details" in values:
                for tax_data in values["group_tax_details"]:
                    tax_values.append(EdiDocument._l10n_ec_prepare_tax_vals_edi(tax_data))
        
        return tax_values

    def _l10n_ec_get_credit_note_edi_taxes(self, taxes_data):
        tax_values = []
        EdiDocument = self.env["account.edi.document"]
        
        if not taxes_data:
            return tax_values
            
        # En Odoo 18.0, usar la nueva estructura de datos
        tax_details = taxes_data.get("tax_details", {})
        
        # Iterar sobre todos los grupos de impuestos 
        for grouping_key, values in tax_details.items():
            # Si el grouping_key es un impuesto (objeto account.tax)
            if hasattr(grouping_key, 'tax_group_id') and hasattr(grouping_key, 'l10n_ec_xml_fe_code'):
                tax_data = {
                    "tax": grouping_key,
                    "base_amount_currency": values.get("base_amount_currency", 0.0),
                    "tax_amount_currency": values.get("tax_amount_currency", 0.0),
                }
                tax_values.append(EdiDocument._l10n_ec_prepare_tax_vals_edi(tax_data))
            
            # Si hay group_tax_details, procesarlos
            elif "group_tax_details" in values:
                for tax_data in values["group_tax_details"]:
                    tax_values.append(EdiDocument._l10n_ec_prepare_tax_vals_edi(tax_data))
        
        return tax_values

    def l10n_ec_get_debit_note_edi_data(self, taxes_data):
        self.ensure_one()
        EdiDocument = self.env["account.edi.document"]
        detail_dict = {
            "descripcion": EdiDocument._l10n_ec_clean_str(
                (self.product_id.name or self.name or "NA")[:300]
            ),
            "precioUnitario": EdiDocument._l10n_ec_number_format(
                self.price_unit, decimals=6
            ),
        }
        return detail_dict
