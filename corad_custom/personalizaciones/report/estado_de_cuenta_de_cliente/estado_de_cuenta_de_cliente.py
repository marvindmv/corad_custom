# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# Estado de Cuenta de Cliente
# Versión con filtro "Solo Facturas / Anticipos sin Asignar"

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    validate_filters(filters)

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def validate_filters(filters):
    if not filters.get("customer"):
        frappe.throw(_("Debe seleccionar un Cliente."))

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("Debe seleccionar un rango de fechas."))


def get_columns():
    return [
        {"label": _("Fecha"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("Tipo"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": _("Documento"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link",
         "options": "voucher_type", "width": 150},

        {"label": _("Contra Documento"), "fieldname": "against_voucher",
         "fieldtype": "Dynamic Link", "options": "against_voucher_type", "width": 150},

        {"label": _("Débito"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Crédito"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Saldo"), "fieldname": "running_balance", "fieldtype": "Currency", "width": 120},
    ]


def get_data(filters):
    customer = filters.get("customer")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    solo_sin_asignar = filters.get("solo_sin_asignar")

    # ------------------------
    # SALDO INICIAL
    # ------------------------
    opening_balance = frappe.db.sql("""
        SELECT SUM(debit) - SUM(credit)
        FROM `tabGL Entry`
        WHERE party_type = 'Customer'
        AND party = %s
        AND posting_date < %s
        AND is_cancelled = 0
    """, (customer, from_date))[0][0] or 0

    data = []

    data.append({
        "posting_date": from_date,
        "voucher_type": "Saldo Inicial",
        "voucher_no": "",
        "against_voucher": "",
        "debit": 0,
        "credit": 0,
        "running_balance": opening_balance,
    })

    # ------------------------
    # MOVIMIENTOS
    # ------------------------
    entries = frappe.db.sql("""
        SELECT
            posting_date,
            voucher_type,
            voucher_no,
            debit,
            credit,
            against_voucher_type,
            against_voucher
        FROM `tabGL Entry`
        WHERE party_type = 'Customer'
        AND party = %s
        AND posting_date BETWEEN %s AND %s
        AND is_cancelled = 0
        ORDER BY posting_date ASC, creation ASC
    """, (customer, from_date, to_date), as_dict=True)

    running_balance = opening_balance

    # Agrupar por documento cuando el checkbox está activo
    grouped = {}

    for row in entries:
        key = row.voucher_no
        if key not in grouped:
            grouped[key] = row

    # ------------------------
    # MODO NORMAL (sin filtro)
    # ------------------------
    if not solo_sin_asignar:
        for row in entries:
            running_balance += flt(row.debit) - flt(row.credit)
            row["running_balance"] = running_balance
            data.append(row)
        return data

    # ------------------------
    # MODO SOLO SIN ASIGNAR
    # ------------------------
    for key, row in grouped.items():

        if not incluir_si_sin_asignar(row):
            continue

        # Contra documento solo para Payment Entry
        if row.voucher_type == "Payment Entry":
            row["against_voucher"] = row.get("against_voucher") or ""
        else:
            row["against_voucher"] = ""

        # Calcular monto pendiente real
        debit = 0
        credit = 0

        if row.voucher_type == "Sales Invoice":
            si = frappe.get_value(
                "Sales Invoice",
                row.voucher_no,
                ["outstanding_amount"],
                as_dict=True,
            )
            monto = flt(si.outstanding_amount or 0)
            debit = monto
            running_balance += monto

        elif row.voucher_type == "Payment Entry":
            pe = frappe.get_value(
                "Payment Entry",
                row.voucher_no,
                ["unallocated_amount"],
                as_dict=True,
            )
            monto = flt(pe.unallocated_amount or 0)
            credit = monto
            running_balance -= monto

        else:
            continue

        row["debit"] = debit
        row["credit"] = credit
        row["running_balance"] = running_balance

        data.append(row)

    return data


def incluir_si_sin_asignar(row):
    doctype = row.voucher_type
    name = row.voucher_no

    if not doctype or not name:
        return False

    if doctype == "Sales Invoice":
        si = frappe.get_value(
            "Sales Invoice",
            name,
            ["outstanding_amount"],
            as_dict=True,
        )
        return flt(si.outstanding_amount or 0) > 0

    if doctype == "Payment Entry":
        pe = frappe.get_value(
            "Payment Entry",
            name,
            ["unallocated_amount"],
            as_dict=True,
        )
        return flt(pe.unallocated_amount or 0) > 0

    return False
