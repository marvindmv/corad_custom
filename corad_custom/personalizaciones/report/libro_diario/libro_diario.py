# Copyright (c) 2026, corad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    data = group_by_voucher(data)

    return columns, data


def get_columns():
    return [
        {"label": "Fecha", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Cuenta", "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 250},
        {"label": "Débito", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Crédito", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Tipo", "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": "Documento", "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
        {"label": "Observación", "fieldname": "remarks", "fieldtype": "Data", "width": 350},
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("from_date"):
        conditions.append("posting_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("account"):
        conditions.append("account = %(account)s")
        values["account"] = filters["account"]

    if filters.get("voucher_type"):
        conditions.append("voucher_type = %(voucher_type)s")
        values["voucher_type"] = filters["voucher_type"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    gl_entries = frappe.db.sql(f"""
        SELECT
            posting_date,
            account,
            debit,
            credit,
            voucher_type,
            voucher_no,
            remarks
        FROM `tabGL Entry`
        WHERE {where_clause}
        ORDER BY posting_date ASC, voucher_no ASC, creation ASC
    """, values, as_dict=True)

    return gl_entries


def group_by_voucher(entries):
    if not entries:
        return []

    grouped = []
    current_voucher = None
    debit_total = 0
    credit_total = 0

    for row in entries:
        voucher = row.voucher_no

        # Si cambia la partida, insertar total + separador
        if current_voucher and voucher != current_voucher:
            grouped.append({
                "posting_date": "",
                "account": f"TOTAL DE PARTIDA {current_voucher}",
                "debit": float(debit_total),
                "credit": float(credit_total),
                "voucher_type": "",
                "voucher_no": "",
                "remarks": "",
            })
            grouped.append({
                "posting_date": "",
                "account": "----------------------------------------",
                "debit": None,
                "credit": None,
                "voucher_type": "",
                "voucher_no": "",
                "remarks": "",
            })
            debit_total = 0
            credit_total = 0

        # Línea normal
        grouped.append({
            "posting_date": row.posting_date,
            "account": row.account,
            "debit": float(row.debit or 0),
            "credit": float(row.credit or 0),
            "voucher_type": row.voucher_type,
            "voucher_no": row.voucher_no,
            "remarks": row.remarks,
        })

        debit_total += row.debit or 0
        credit_total += row.credit or 0

        current_voucher = voucher

    # Última partida
    if current_voucher:
        grouped.append({
            "posting_date": "",
            "account": f"TOTAL DE PARTIDA {current_voucher}",
            "debit": float(debit_total),
            "credit": float(credit_total),
            "voucher_type": "",
            "voucher_no": "",
            "remarks": "",
        })
        grouped.append({
            "posting_date": "",
            "account": "----------------------------------------",
            "debit": None,
            "credit": None,
            "voucher_type": "",
            "voucher_no": "",
            "remarks": "",
        })

    return grouped
