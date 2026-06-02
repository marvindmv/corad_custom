// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Arqueo de caja"] = {
    "filters": [
        {
            "fieldname": "desde",
            "label": "Desde",
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "hasta",
            "label": "Hasta",
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "payment_type",
            "label": "Tipo de Pago",
            "fieldtype": "Select",
            "options": "\nReceive\nPay\nInternal Transfer",
            "reqd": 0,
            "on_change": function(report) {
                report.refresh();
            }
        }
    ]
};
