# Copyright (c) 2026, corad and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate

value_fields = ("opening_debit", "opening_credit", "debit", "credit", "closing_debit", "closing_credit")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    accounts = get_accounts(filters.company)
    if not accounts:
        return columns, []

    company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")

    opening_map = get_opening_balances(filters)
    gl_entries = get_gl_entries(filters)
    gl_by_account = group_gl_by_account(gl_entries)

    total_row = calculate_values(accounts, gl_by_account, opening_map, company_currency)
    accounts_by_name = {d.name: d for d in accounts}
    accumulate_values_into_parents(accounts, accounts_by_name)

    data = prepare_data(accounts, filters, total_row, company_currency)

    # expandir con detalle de movimientos por cuenta no grupo
    final_rows = []
    for d in data:
        # filas de total (al final) o separadores
        if not d.get("account"):
            final_rows.append(d)
            continue

        final_rows.append(d)

        # si es cuenta de movimiento, agregar detalle
        if not d.get("is_group") and d.get("has_value"):
            details = gl_by_account.get(d["account"], [])
            for e in details:
                final_rows.append({
                    "fecha": e.posting_date,
                    "documento": e.voucher_no,
                    "account": e.remarks or e.account,
                    "opening_debit": 0.0,
                    "opening_credit": 0.0,
                    "debit": flt(e.debit),
                    "credit": flt(e.credit),
                    "closing_debit": 0.0,
                    "closing_credit": 0.0,
                    "currency": company_currency
                })

    # filtrar filas en cero si el usuario no marcó "mostrar valores en cero"
    if not filters.get("show_zero_values"):
        cleaned = []
        for r in final_rows:
            if not r.get("account"):
                cleaned.append(r)
                continue
            if any(abs(flt(r.get(k))) >= 0.005 for k in value_fields):
                cleaned.append(r)
        final_rows = cleaned

    return columns, final_rows


def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Compañía es requerida"))

    if not filters.from_date or not filters.to_date:
        frappe.throw(_("Desde y Hasta son requeridos"))

    filters.from_date = getdate(filters.from_date)
    filters.to_date = getdate(filters.to_date)

    if filters.from_date > filters.to_date:
        frappe.throw(_("Desde no puede ser mayor que Hasta"))


def get_accounts(company):
    return frappe.db.sql(
        """
        SELECT
            name,
            account_number,
            parent_account,
            account_name,
            root_type,
            is_group,
            lft,
            rgt
        FROM `tabAccount`
        WHERE company = %s
        ORDER BY lft
        """,
        (company,),
        as_dict=True,
    )


def get_opening_balances(filters):
    gle = frappe.db.sql(
        """
        SELECT
            account,
            SUM(debit) AS opening_debit,
            SUM(credit) AS opening_credit
        FROM `tabGL Entry`
        WHERE
            company = %(company)s
            AND posting_date < %(from_date)s
        GROUP BY account
        """,
        {
            "company": filters.company,
            "from_date": filters.from_date,
        },
        as_dict=True,
    )

    opening = frappe._dict()
    for d in gle:
        opening.setdefault(d.account, d)
    return opening


def get_gl_entries(filters):
    return frappe.db.sql(
        """
        SELECT
            posting_date,
            account,
            debit,
            credit,
            voucher_type,
            voucher_no,
            remarks
        FROM `tabGL Entry`
        WHERE
            company = %(company)s
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY account, posting_date, voucher_no
        """,
        {
            "company": filters.company,
            "from_date": filters.from_date,
            "to_date": filters.to_date,
        },
        as_dict=True,
    )


def group_gl_by_account(gl_entries):
    out = {}
    for e in gl_entries:
        out.setdefault(e.account, []).append(e)
    return out


def calculate_values(accounts, gl_by_account, opening_balances, company_currency):
    init = {
        "opening_debit": 0.0,
        "opening_credit": 0.0,
        "debit": 0.0,
        "credit": 0.0,
        "closing_debit": 0.0,
        "closing_credit": 0.0,
    }

    total_row = {
        "account": _("Total"),
        "account_name": _("Total"),
        "opening_debit": 0.0,
        "opening_credit": 0.0,
        "debit": 0.0,
        "credit": 0.0,
        "closing_debit": 0.0,
        "closing_credit": 0.0,
        "parent_account": None,
        "indent": 0,
        "has_value": True,
        "currency": company_currency,
        "is_group": 0,
    }

    for d in accounts:
        d.update(init.copy())

        op = opening_balances.get(d.name, {})
        d["opening_debit"] = flt(op.get("opening_debit", 0.0))
        d["opening_credit"] = flt(op.get("opening_credit", 0.0))

        for entry in gl_by_account.get(d.name, []):
            d["debit"] += flt(entry.debit)
            d["credit"] += flt(entry.credit)

        total_row["debit"] += d["debit"]
        total_row["credit"] += d["credit"]
        total_row["opening_debit"] += d["opening_debit"]
        total_row["opening_credit"] += d["opening_credit"]

    return total_row


def accumulate_values_into_parents(accounts, accounts_by_name):
    for d in reversed(accounts):
        if d.parent_account:
            parent = accounts_by_name.get(d.parent_account)
            if not parent:
                continue
            for key in value_fields:
                parent[key] = parent.get(key, 0.0) + d.get(key, 0.0)


def prepare_data(accounts, filters, total_row, company_currency):
    data = []

    total_row["closing_debit"] = 0.0
    total_row["closing_credit"] = 0.0

    for d in accounts:
        has_value = False

        row = {
            "account": d.name,
            "parent_account": d.parent_account,
            "from_date": filters.from_date,
            "to_date": filters.to_date,
            "is_group": d.is_group,
            "currency": company_currency,
            "account_name": (
                "{} - {}".format(d.account_number, d.account_name)
                if d.account_number
                else d.account_name
            ),
        }

        prepare_opening_and_closing(d)

        for key in value_fields:
            row[key] = flt(d.get(key, 0.0), 3)
            if abs(row[key]) >= 0.005:
                has_value = True

        row["has_value"] = has_value

        # fila resumen de cuenta (sin fecha/documento)
        data.append(
            {
                "fecha": None,
                "documento": None,
                "account": row["account_name"],
                "opening_debit": row["opening_debit"],
                "opening_credit": row["opening_credit"],
                "debit": row["debit"],
                "credit": row["credit"],
                "closing_debit": row["closing_debit"],
                "closing_credit": row["closing_credit"],
                "currency": row["currency"],
                "is_group": d.is_group,
                "has_value": has_value,
                "account_internal": d.name,
            }
        )

        if not d.parent_account:
            diff = d["debit"] - d["credit"]
            if diff > 0:
                total_row["closing_debit"] += diff
            elif diff < 0:
                total_row["closing_credit"] += abs(diff)

    # fila vacía + total
    data.append({})
    data.append(
        {
            "fecha": None,
            "documento": None,
            "account": total_row["account_name"],
            "opening_debit": flt(total_row["opening_debit"], 3),
            "opening_credit": flt(total_row["opening_credit"], 3),
            "debit": flt(total_row["debit"], 3),
            "credit": flt(total_row["credit"], 3),
            "closing_debit": flt(total_row["closing_debit"], 3),
            "closing_credit": flt(total_row["closing_credit"], 3),
            "currency": total_row["currency"],
            "is_group": 0,
            "has_value": True,
            "account_internal": None,
        }
    )

    # mapear account_internal → account real para detalle
    for r in data:
        if r.get("account_internal"):
            r["account"] = r["account_internal"]

    return data


def get_columns():
    return [
        {
            "label": _("Fecha"),
            "fieldname": "fecha",
            "fieldtype": "Date",
            "width": 80,
        },
        {
            "label": _("Documento"),
            "fieldname": "documento",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Cuenta"),
            "fieldname": "account",
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "fieldname": "opening_debit",
            "label": _("Inicial Db."),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "opening_credit",
            "label": _("Inicial Cr"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "debit",
            "label": _("Debito"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "credit",
            "label": _("Credito"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "closing_debit",
            "label": _("Saldo Debito"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "closing_credit",
            "label": _("Saldo Credito"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "fieldname": "currency",
            "label": _("Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "hidden": 1,
        },
    ]


def prepare_opening_and_closing(d):
    d["closing_debit"] = d["opening_debit"] + d["debit"]
    d["closing_credit"] = d["opening_credit"] + d["credit"]

    if d["closing_debit"] > d["closing_credit"]:
        d["closing_debit"] -= d["closing_credit"]
        d["closing_credit"] = 0.0
    else:
        d["closing_credit"] -= d["closing_debit"]
        d["closing_debit"] = 0.0

    if d["opening_debit"] > d["opening_credit"]:
        d["opening_debit"] -= d["opening_credit"]
        d["opening_credit"] = 0.0
    else:
        d["opening_credit"] -= d["opening_debit"]
        d["opening_debit"] = 0.0
