/** @odoo-module */

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

const actionRegistry = registry.category("actions");
const TaxReportAction = actionRegistry.get("tax_r");

if (TaxReportAction && !TaxReportAction.prototype.exportAtsXml) {
    TaxReportAction.prototype.exportAtsXml = async function () {
        const filters = this.filter();
        const startDate = filters.start_date || this.start_date.el.value;
        const endDate = filters.end_date || this.end_date.el.value;

        await download({
            url: "/l10n_ec_ats/export_xml",
            data: {
                start_date: startDate,
                end_date: endDate,
            },
        });
    };
}
