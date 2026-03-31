// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Estado de Cuenta de Cliente"] = {
    "filters": [
        {
            "fieldname": "customer",
            "label": __("Cliente"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 1,
            "on_change": function(query_report) {
                let customer = frappe.query_report.get_filter_value("customer");
                if (customer) {
                    frappe.db.get_value("Customer", customer, "customer_name", function(r) {
                        frappe.query_report.set_filter_value("customer_name", r.customer_name);
                    });
                }
            }
        },
        {
            "fieldname": "customer_name",
            "label": __("Nombre del Cliente"),
            "fieldtype": "Data",
            "read_only": 1
        },
        {
            "fieldname": "from_date",
            "label": __("Desde"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("Hasta"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
	{ "fieldname": "solo_sin_asignar",
	  "label": __("Solo Facturas / Anticipos sin Asignar"),
	  "fieldtype": "Check", "default": 0
	}

    ]
}
