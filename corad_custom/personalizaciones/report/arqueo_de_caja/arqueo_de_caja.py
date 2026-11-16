# Copyright (c) 2025, Frappe Technologies Pvt. Ltd.
# For license information, please see license.txt

import frappe

def execute(filters=None):
    fecha_desde = filters.get("desde")
    fecha_hasta = filters.get("hasta")
    payment_type = filters.get("payment_type")

    # -----------------------------
    # 1) CONDICIÓN DINÁMICA
    # -----------------------------
    cond_payment_type = ""
    params_detalle = [fecha_desde, fecha_hasta]

    if payment_type:
        cond_payment_type = " AND pe.payment_type = %s"
        params_detalle.append(payment_type)

    # -----------------------------
    # 2) DETALLE POR FACTURA
    # -----------------------------
    data = frappe.db.sql(f"""
        SELECT
            pe.posting_date AS fecha,
            pe.name AS payment_entry,
            pe.party AS codigo_cliente,
            pe.party_name AS cliente,
            pe.remarks AS concepto,
            per.allocated_amount AS monto,
            pe.mode_of_payment AS metodo_pago,
            pe.owner AS cajero,
            per.reference_name AS factura
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per
            ON per.parent = pe.name
            AND per.reference_doctype = 'Sales Invoice'
        WHERE pe.docstatus = 1
        AND pe.posting_date BETWEEN %s AND %s
        AND per.reference_name IS NOT NULL
        {cond_payment_type}
        ORDER BY pe.creation ASC
    """, params_detalle, as_dict=True)

    # -----------------------------
    # 3) RESUMEN PARA ANTICIPOS
    # -----------------------------
    cond_payment_type2 = ""
    params_anticipos = [fecha_desde, fecha_hasta]

    if payment_type:
        cond_payment_type2 = " AND pe.payment_type = %s"
        params_anticipos.append(payment_type)

    anticipos = frappe.db.sql(f"""
        SELECT
            pe.name AS payment_entry,
            pe.posting_date AS fecha,
            pe.party AS codigo_cliente,
            pe.party_name AS cliente,
            pe.remarks AS concepto,
            pe.paid_amount AS total_pagado,
            COALESCE(SUM(per.allocated_amount), 0) AS total_asignado,
            COUNT(per.name) AS cantidad_referencias,
            pe.mode_of_payment AS metodo_pago,
            pe.owner AS cajero
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per
            ON per.parent = pe.name
            AND per.reference_doctype = 'Sales Invoice'
        WHERE pe.docstatus = 1
        AND pe.posting_date BETWEEN %s AND %s
        {cond_payment_type2}
        GROUP BY pe.name
    """, params_anticipos, as_dict=True)

    # -----------------------------
    # 4) AGREGAR ANTICIPOS
    # -----------------------------
    for a in anticipos:
        monto_sin_asignar = a.total_pagado - a.total_asignado

        if a.cantidad_referencias == 0 and a.total_pagado > 0:
            data.append({
                "fecha": a.fecha,
                "payment_entry": a.payment_entry,
                "codigo_cliente": a.codigo_cliente,
                "cliente": a.cliente,
                "factura": "",
                "concepto": "ANTICIPO / MONTO SIN ASIGNAR",
                "metodo_pago": a.metodo_pago,
                "cajero": a.cajero,
                "monto": a.total_pagado
            })

        elif monto_sin_asignar > 0:
            data.append({
                "fecha": a.fecha,
                "payment_entry": a.payment_entry,
                "codigo_cliente": a.codigo_cliente,
                "cliente": a.cliente,
                "factura": "",
                "concepto": "ANTICIPO / MONTO SIN ASIGNAR",
                "metodo_pago": a.metodo_pago,
                "cajero": a.cajero,
                "monto": monto_sin_asignar
            })

    # Ordenar por documento
    data.sort(key=lambda x: x.get("payment_entry") or "")

    # -----------------------------
    # 5) TOTALES DESDE EL DETALLE
    # -----------------------------
    totales_por_metodo = {}
    total_general = 0

    for d in data:
        monto = d.get("monto") or 0
        metodo = d.get("metodo_pago") or ""

        total_general += monto

        if metodo not in totales_por_metodo:
            totales_por_metodo[metodo] = 0

        totales_por_metodo[metodo] += monto

    # -----------------------------
    # 6) COLUMNAS
    # -----------------------------
    columns = [
        {"label": "Fecha", "fieldname": "fecha", "fieldtype": "Date", "width": 100},
        {"label": "Documento", "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
        {"label": "Código Cliente", "fieldname": "codigo_cliente", "fieldtype": "Data", "width": 120},
        {"label": "Cliente", "fieldname": "cliente", "fieldtype": "Data", "width": 200},
        {"label": "Factura", "fieldname": "factura", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": "Concepto", "fieldname": "concepto", "fieldtype": "Data", "width": 300},
        {"label": "Método de Pago", "fieldname": "metodo_pago", "fieldtype": "Data", "width": 150},
        {"label": "Cajero", "fieldname": "cajero", "fieldtype": "Data", "width": 150},
        {"label": "Monto", "fieldname": "monto", "fieldtype": "Currency", "width": 120},
    ]

    # -----------------------------
    # 7) AGREGAR TOTALES POR MÉTODO
    # -----------------------------
    for metodo, total in totales_por_metodo.items():
        data.append({
            "fecha": "",
            "payment_entry": "",
            "codigo_cliente": "",
            "cliente": "",
            "factura": "",
            "concepto": f"TOTAL {metodo}",
            "metodo_pago": metodo,
            "cajero": "",
            "monto": total
        })

    # TOTAL GENERAL
    data.append({
        "fecha": "",
        "payment_entry": "",
        "codigo_cliente": "",
        "cliente": "",
        "factura": "",
        "concepto": "TOTAL GENERAL",
        "metodo_pago": "",
        "cajero": "",
        "monto": total_general
    })

    return columns, data
