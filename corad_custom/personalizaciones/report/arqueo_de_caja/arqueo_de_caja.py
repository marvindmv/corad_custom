# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    fecha_desde = filters.get("desde")
    fecha_hasta = filters.get("hasta")

    # Detalle por referencia (solo líneas que tienen factura)
    data = frappe.db.sql("""
        SELECT
            TIME(pe.creation) AS hora,
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
        ORDER BY pe.creation ASC
    """, (fecha_desde, fecha_hasta), as_dict=True)

    # Resumen por Payment Entry para calcular monto sin asignar
    anticipos = frappe.db.sql("""
        SELECT
            pe.name AS payment_entry,
            TIME(pe.creation) AS hora,
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
        GROUP BY pe.name
    """, (fecha_desde, fecha_hasta), as_dict=True)

    # Agregar filas de anticipo / monto sin asignar
    for a in anticipos:
        monto_sin_asignar = a.total_pagado - a.total_asignado

        # Caso 1: Payment Entry sin ninguna referencia -> anticipo puro
        if a.cantidad_referencias == 0 and a.total_pagado > 0:
            data.append({
                "hora": a.hora,
                "payment_entry": a.payment_entry,
                "codigo_cliente": a.codigo_cliente,
                "cliente": a.cliente,
                "factura": "",
                "concepto": "ANTICIPO / MONTO SIN ASIGNAR",
                "metodo_pago": a.metodo_pago,
                "cajero": a.cajero,
                "monto": a.total_pagado
            })
        # Caso 2: Tiene referencias pero no todo está asignado -> anticipo parcial
        elif monto_sin_asignar > 0:
            data.append({
                "hora": a.hora,
                "payment_entry": a.payment_entry,
                "codigo_cliente": a.codigo_cliente,
                "cliente": a.cliente,
                "factura": "",
                "concepto": "ANTICIPO / MONTO SIN ASIGNAR",
                "metodo_pago": a.metodo_pago,
                "cajero": a.cajero,
                "monto": monto_sin_asignar
            })

    # Ordenar filas de detalle por documento
    data.sort(key=lambda x: x.get("payment_entry") or "")

    # Totales por método (siempre igual a suma de paid_amount por método)
    totales_por_metodo = frappe.db.sql("""
        SELECT
            metodo_pago AS metodo,
            SUM(monto) AS total
        FROM (
            -- Parte asignada a facturas
            SELECT
                pe.mode_of_payment AS metodo_pago,
                COALESCE(per.allocated_amount, 0) AS monto
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabPayment Entry Reference` per
                ON per.parent = pe.name
                AND per.reference_doctype = 'Sales Invoice'
            WHERE pe.docstatus = 1
            AND pe.posting_date BETWEEN %s AND %s

            UNION ALL

            -- Monto sin asignar (anticipos)
            SELECT
                pe.mode_of_payment AS metodo_pago,
                (pe.paid_amount - COALESCE(SUM(per.allocated_amount), 0)) AS monto
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabPayment Entry Reference` per
                ON per.parent = pe.name
                AND per.reference_doctype = 'Sales Invoice'
            WHERE pe.docstatus = 1
            AND pe.posting_date BETWEEN %s AND %s
            GROUP BY pe.name
        ) AS t
        GROUP BY metodo_pago
    """, (fecha_desde, fecha_hasta, fecha_desde, fecha_hasta), as_dict=True)

    # Total general desde el detalle
    total_general = sum([d.get("monto", 0) for d in data])

    columns = [
        {"label": "Hora", "fieldname": "hora", "fieldtype": "Time", "width": 80},
        {"label": "Documento", "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
        {"label": "Código Cliente", "fieldname": "codigo_cliente", "fieldtype": "Data", "width": 120},
        {"label": "Cliente", "fieldname": "cliente", "fieldtype": "Data", "width": 200},
        {"label": "Factura", "fieldname": "factura", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": "Concepto", "fieldname": "concepto", "fieldtype": "Data", "width": 300},
        {"label": "Método de Pago", "fieldname": "metodo_pago", "fieldtype": "Data", "width": 150},
        {"label": "Cajero", "fieldname": "cajero", "fieldtype": "Data", "width": 150},
        {"label": "Monto", "fieldname": "monto", "fieldtype": "Currency", "width": 120},
    ]

    # Agregar totales por método
    for t in totales_por_metodo:
        data.append({
            "hora": "",
            "payment_entry": "",
            "codigo_cliente": "",
            "cliente": "",
            "factura": "",
            "concepto": f"TOTAL {t.metodo}",
            "metodo_pago": t.metodo,
            "cajero": "",
            "monto": t.total
        })

    # Total general
    data.append({
        "hora": "",
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
