# Copyright (c) 2026, corad and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    # Validación para evitar ejecución sin filtros
    if not filters.get("account") or not filters.get("from_date") or not filters.get("to_date"):
        return get_columns(), []

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Fecha de Contabilización", "fieldname": "posting_date", "fieldtype": "Data", "width": 120},
        {"label": "Entrada de Pago", "fieldname": "voucher_no", "fieldtype": "Data", "width": 140},
        {"label": "Movimiento", "fieldname": "voucher_type", "fieldtype": "Data", "width": 140},
        {"label": "Cheque / No de Referencia", "fieldname": "reference", "fieldtype": "Data", "width": 180},
        {"label": "Descripción", "fieldname": "remarks", "fieldtype": "Data", "width": 250},
        {"label": "Cuenta", "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 250},
        {"label": "Debe", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Haber", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Saldo", "fieldname": "running_balance", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters):
    data = []
    running_balance = 0

    # 1. SALDO DE APERTURA
    opening = frappe.db.sql("""
        SELECT SUM(debit) - SUM(credit)
        FROM `tabGL Entry`
        WHERE account = %(account)s
          AND posting_date < %(from_date)s
          AND is_cancelled = 0
    """, filters)

    opening_balance = opening[0][0] or 0

    data.append({
        "posting_date": "Apertura",
        "debit": opening_balance if opening_balance > 0 else 0,
        "credit": abs(opening_balance) if opening_balance < 0 else 0,
        "running_balance": opening_balance,
        "remarks": "",
        "reference": "",
        "voucher_no": "",
        "voucher_type": "",
        "account": filters.get("account")
    })

    running_balance = opening_balance

    # 2. MOVIMIENTOS DEL PERIODO (SOLO VÁLIDOS, NO ANULADOS)
    entries = frappe.db.sql("""
        SELECT
            gle.posting_date,
            gle.voucher_no,
            gle.voucher_type,
            gle.remarks,
            gle.account,
            gle.debit,
            gle.credit,
            COALESCE(pe.reference_no, je.cheque_no, gle.against_voucher) AS reference
        FROM `tabGL Entry` gle
        LEFT JOIN `tabPayment Entry` pe ON pe.name = gle.voucher_no
        LEFT JOIN `tabJournal Entry` je ON je.name = gle.voucher_no
        WHERE gle.account = %(account)s
          AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND gle.is_cancelled = 0
        ORDER BY gle.posting_date, gle.creation
    """, filters, as_dict=True)

    for e in entries:
        running_balance += (e.debit - e.credit)
        e["running_balance"] = running_balance
        data.append(e)

    return data
