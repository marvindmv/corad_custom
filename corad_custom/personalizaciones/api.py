# ~/frappe-bench/apps/corad_custom/corad_custom/personalizaciones/api.py

import frappe
import json
from frappe.utils import getdate

# ============================================
# MÉTODO PARA FACTURA DE COMPRA
# ============================================

@frappe.whitelist(allow_guest=False)
def obtener_datos_json():
    """
    Obtiene los datos del JSON y los prepara para llenar el formulario de Factura de Compra
    """
    try:
        # Obtener los datos del request
        data = frappe.local.form_dict.get('data')
        
        if not data:
            return {
                "status": "error",
                "message": "No se recibieron datos"
            }
        
        # Parsear JSON
        if isinstance(data, str):
            data = json.loads(data)
        
        # Validación de estructura
        if not data.get('identificacion'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta identificacion)"
            }
        
        if not data.get('emisor'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta emisor)"
            }
        
        if not data.get('receptor'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta receptor)"
            }
        
        # --- DETECTAR TIPO DE FACTURA ---
        tipo_dte = data.get('identificacion', {}).get('tipoDte', '')
        es_sujeto_excluido = tipo_dte == "14"
        
        tipo_descripcion = {
            "01": "Factura",
            "03": "Factura de Compra (CCF)",
            "05": "Nota de Crédito",
            "06": "Nota de Débito",
            "11": "Factura de Exportación",
            "14": "Sujeto Excluido (SE)"
        }.get(tipo_dte, f"Tipo {tipo_dte}")
        
        # --- 1. DATOS DEL PROVEEDOR ---
        if es_sujeto_excluido:
            receptor = data.get('receptor', {})
            nombre_proveedor = receptor.get('nombre', '').strip() if receptor else ''
            nit_proveedor = receptor.get('numDocumento', '').strip() if receptor else ''
        else:
            emisor = data.get('emisor', {})
            nombre_proveedor = emisor.get('nombre', '').strip() if emisor else ''
            nit_proveedor = emisor.get('nit', '').strip() if emisor else ''
        
        if not nombre_proveedor:
            return {
                "status": "error",
                "message": "Falta el nombre del proveedor"
            }
        
        # Buscar proveedor por nombre exacto
        proveedor = frappe.db.get_value('Supplier', {'supplier_name': nombre_proveedor}, 'name')
        
        # Si no encuentra por nombre exacto, buscar por nombre que contenga
        if not proveedor:
            proveedores = frappe.db.get_list('Supplier', 
                filters={'supplier_name': ['like', '%' + nombre_proveedor + '%']},
                pluck='name',
                limit=1
            )
            if proveedores:
                proveedor = proveedores[0]
        
        proveedor_data = {
            "exists": bool(proveedor),
            "name": proveedor if proveedor else None,
            "supplier_name": nombre_proveedor,
            "tax_id": nit_proveedor
        }
        
        # --- 2. DATOS DE LA FACTURA ---
        identificacion = data.get('identificacion', {})
        
        try:
            fecha_str = identificacion.get('fecEmi', '')
            if fecha_str:
                fecha_emision = getdate(fecha_str)
            else:
                fecha_emision = getdate()
        except:
            fecha_emision = getdate()
        
        codigo_generacion = identificacion.get('codigoGeneracion', '')
        numero_control = identificacion.get('numeroControl', '')
        sello_recibido = data.get('selloRecibido', '')
        
        # --- 3. DTE ---
        dte_texto = f"numeroControl\t: {numero_control}\n"
        dte_texto += f"codigoGeneracion\t: {codigo_generacion}\n"
        dte_texto += f"selloRecibido\t: {sello_recibido}\n"
        dte_texto += f"tipoDte\t\t: {tipo_dte} - {tipo_descripcion}"
        
        # --- 4. OBSERVACIONES DEL JSON ---
        observaciones_json = ""
        
        # Buscar en resumen.observaciones
        resumen = data.get('resumen', {})
        observaciones_json = resumen.get('observaciones', '')
        
        # Si no hay, buscar en extension.observaciones
        if not observaciones_json:
            extension = data.get('extension', {})
            if extension and isinstance(extension, dict):
                observaciones_json = extension.get('observaciones', '')
        
        # Si sigue vacío, buscar en apendice
        if not observaciones_json:
            apendice = data.get('apendice', [])
            if apendice and isinstance(apendice, list):
                for item in apendice:
                    if item.get('campo') == 'OBSERVACION':
                        observaciones_json = item.get('valor', '')
                        break
        
        # --- 5. PROCESAR ITEMS ---
        # UOM siempre "Nos." para todos los casos
        uom_default = "Nos."
        
        items = []
        observaciones_items = []
        
        # Verificar que existe cuerpoDocumento
        cuerpo_documento = data.get('cuerpoDocumento', [])
        
        if not cuerpo_documento:
            return {
                "status": "warning",
                "message": "El JSON no contiene items en cuerpoDocumento"
            }
        
        # Verificar/Crear Grupo de Productos por defecto
        item_group = "Productos"
        if not frappe.db.exists('Item Group', item_group):
            try:
                grupos_existentes = frappe.db.get_list('Item Group', pluck='name', limit=1)
                if grupos_existentes:
                    item_group = grupos_existentes[0]
                else:
                    nuevo_grupo = frappe.get_doc({
                        "doctype": "Item Group",
                        "item_group_name": item_group,
                        "parent_item_group": "All Item Groups"
                    })
                    nuevo_grupo.insert(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Error creando grupo de productos: {str(e)}", "Importación JSON")
                grupos_existentes = frappe.db.get_list('Item Group', pluck='name', limit=1)
                if grupos_existentes:
                    item_group = grupos_existentes[0]
                else:
                    item_group = "All Item Groups"
        
        # Verificar/Crear Unidad de Medida "Nos." si no existe
        if not frappe.db.exists('UOM', uom_default):
            try:
                uoms_existentes = frappe.db.get_list('UOM', pluck='name', limit=1)
                if uoms_existentes:
                    uom_default = uoms_existentes[0]
                else:
                    nueva_uom = frappe.get_doc({
                        "doctype": "UOM",
                        "uom_name": "Nos."
                    })
                    nueva_uom.insert(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Error creando UOM: {str(e)}", "Importación JSON")
                uoms_existentes = frappe.db.get_list('UOM', pluck='name', limit=1)
                if uoms_existentes:
                    uom_default = uoms_existentes[0]
                else:
                    uom_default = "Nos."
        
        for item_json in cuerpo_documento:
            codigo = item_json.get('codigo', "ITEM-001")
            descripcion = item_json.get('descripcion', 'Sin descripción')
            cantidad = item_json.get('cantidad', 1)
            precio = item_json.get('precioUni', 0)
            
            # SIEMPRE usar "Nos." como UOM, ignorando el campo uniMedida
            uom = uom_default
            
            # Buscar item por código
            item = frappe.db.get_value('Item', {'item_code': codigo}, 'name')
            
            items.append({
                "item_code": codigo,
                "item_name": descripcion[:140] if descripcion else "Sin descripción",
                "description": descripcion,
                "qty": cantidad,
                "rate": precio,
                "uom": uom,
                "exists": bool(item),
                "item_id": item if item else None
            })
            
            observaciones_items.append(f"{cantidad} {descripcion} ${precio:.2f}")
        
        # --- 6. CONSTRUIR RESPUESTA ---
        return {
            "status": "success",
            "data": {
                "tipo_dte": tipo_dte,
                "tipo_descripcion": tipo_descripcion,
                "es_sujeto_excluido": es_sujeto_excluido,
                "supplier": proveedor_data,
                "bill_no": codigo_generacion,
                "bill_date": fecha_emision.strftime("%Y-%m-%d") if fecha_emision else "",
                "posting_date": fecha_emision.strftime("%Y-%m-%d") if fecha_emision else "",
                "due_date": fecha_emision.strftime("%Y-%m-%d") if fecha_emision else "",
                "dte": dte_texto,
                "items": items,
                "observaciones_items": observaciones_items,
                "observaciones_json": observaciones_json,
                "total": data.get('resumen', {}).get('totalPagar', 0),
                "subtotal": data.get('resumen', {}).get('subTotal', 0),
                "currency": data.get('identificacion', {}).get('tipoMoneda', 'USD')
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            title="Error procesando JSON Compra",
            message=f"Error: {error_msg}"
        )
        return {
            "status": "error",
            "message": f"Error interno: {error_msg}"
        }

# ============================================
#  FACTURA DE VENTA
# ============================================

# ============================================
# FUNCIÓN AUXILIAR: Formatear código a 5 dígitos
# ============================================

def formatear_codigo(codigo):
    """
    Formatea un código a 5 dígitos con ceros a la izquierda
    Ejemplo: "1" → "00001", "5" → "00005"
    """
    if not codigo:
        return "00001"
    
    codigo_str = str(codigo).strip()
    
    if len(codigo_str) >= 5:
        return codigo_str.zfill(5)
    
    try:
        num = int(codigo_str)
        return f"{num:05d}"
    except ValueError:
        return codigo_str.zfill(5)


# ============================================
# MÉTODO PARA FACTURA DE VENTA
# ============================================

@frappe.whitelist(allow_guest=False)
def obtener_datos_json_venta():
    """
    Obtiene los datos del JSON y los prepara para llenar el formulario de Factura de Venta
    """
    try:
        # Obtener los datos del request
        data = frappe.local.form_dict.get('data')
        
        if not data:
            return {
                "status": "error",
                "message": "No se recibieron datos"
            }
        
        # Parsear JSON
        if isinstance(data, str):
            data = json.loads(data)
        
        # Validación de estructura
        if not data.get('identificacion'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta identificacion)"
            }
        
        if not data.get('emisor'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta emisor)"
            }
        
        if not data.get('receptor'):
            return {
                "status": "error",
                "message": "El JSON no tiene la estructura esperada (falta receptor)"
            }
        
        # --- DETECTAR TIPO DE FACTURA ---
        tipo_dte = data.get('identificacion', {}).get('tipoDte', '')
        
        tipo_descripcion = {
            "01": "Consumidor Final",
            "03": "Crédito Fiscal (CCF)",
            "05": "Nota de Crédito",
            "06": "Nota de Débito",
            "11": "Factura de Exportación"
        }.get(tipo_dte, f"Tipo {tipo_dte}")
        
        # --- 1. DATOS DEL CLIENTE (SIEMPRE EL RECEPTOR) ---
        receptor = data.get('receptor', {})
        nombre_cliente = receptor.get('nombre', '').strip() if receptor else ''
        
        if not nombre_cliente:
            return {
                "status": "error",
                "message": "Falta el nombre del cliente en el receptor"
            }
        
        # Buscar cliente por nombre exacto
        cliente = frappe.db.get_value('Customer', {'customer_name': nombre_cliente}, 'name')
        
        # Si no encuentra por nombre exacto, buscar por nombre que contenga
        if not cliente:
            clientes = frappe.db.get_list('Customer', 
                filters={'customer_name': ['like', '%' + nombre_cliente + '%']},
                pluck='name',
                limit=1
            )
            if clientes:
                cliente = clientes[0]
        
        cliente_data = {
            "exists": bool(cliente),
            "name": cliente if cliente else None,
            "customer_name": nombre_cliente
        }
        
        # --- 2. DATOS DE LA FACTURA ---
        identificacion = data.get('identificacion', {})
        
        try:
            fecha_str = identificacion.get('fecEmi', '')
            if fecha_str:
                fecha_emision = getdate(fecha_str)
            else:
                fecha_emision = getdate()
        except:
            fecha_emision = getdate()
        
        codigo_generacion = identificacion.get('codigoGeneracion', '')
        numero_control = identificacion.get('numeroControl', '')
        sello_recibido = data.get('selloRecibido', '')
        
        # --- 3. DTE ---
        dte_texto = f"numeroControl\t: {numero_control}\n"
        dte_texto += f"codigoGeneracion\t: {codigo_generacion}\n"
        dte_texto += f"selloRecibido\t: {sello_recibido}\n"
        dte_texto += f"tipoDte\t\t: {tipo_dte} - {tipo_descripcion}"
        
        # --- 4. OBSERVACIONES DEL JSON ---
        observaciones_json = ""
        
        resumen = data.get('resumen', {})
        observaciones_json = resumen.get('observaciones', '')
        
        if not observaciones_json:
            extension = data.get('extension', {})
            if extension and isinstance(extension, dict):
                observaciones_json = extension.get('observaciones', '')
        
        # --- 5. PROCESAR ITEMS ---
        uom_default = "Nos."
        
        items = []
        observaciones_items = []
        
        cuerpo_documento = data.get('cuerpoDocumento', [])
        
        if not cuerpo_documento:
            return {
                "status": "warning",
                "message": "El JSON no contiene items en cuerpoDocumento"
            }
        
        # Verificar/Crear Grupo de Productos
        item_group = "Productos"
        if not frappe.db.exists('Item Group', item_group):
            try:
                grupos_existentes = frappe.db.get_list('Item Group', pluck='name', limit=1)
                if grupos_existentes:
                    item_group = grupos_existentes[0]
                else:
                    nuevo_grupo = frappe.get_doc({
                        "doctype": "Item Group",
                        "item_group_name": item_group,
                        "parent_item_group": "All Item Groups"
                    })
                    nuevo_grupo.insert(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Error creando grupo de productos: {str(e)}", "Importación JSON Venta")
                grupos_existentes = frappe.db.get_list('Item Group', pluck='name', limit=1)
                if grupos_existentes:
                    item_group = grupos_existentes[0]
        
        # Verificar/Crear Unidad de Medida
        if not frappe.db.exists('UOM', uom_default):
            try:
                uoms_existentes = frappe.db.get_list('UOM', pluck='name', limit=1)
                if uoms_existentes:
                    uom_default = uoms_existentes[0]
                else:
                    nueva_uom = frappe.get_doc({
                        "doctype": "UOM",
                        "uom_name": "Nos."
                    })
                    nueva_uom.insert(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Error creando UOM: {str(e)}", "Importación JSON Venta")
                uoms_existentes = frappe.db.get_list('UOM', pluck='name', limit=1)
                if uoms_existentes:
                    uom_default = uoms_existentes[0]
        
        for item_json in cuerpo_documento:
            # --- FORMATEO DE CÓDIGO A 5 DÍGITOS ---
            codigo_original = item_json.get('codigo', '1')
            codigo = formatear_codigo(codigo_original)
            
            descripcion = item_json.get('descripcion', 'Sin descripción')
            cantidad = item_json.get('cantidad', 1)
            precio = item_json.get('precioUni', 0)
            
            uom = uom_default
            
            item = frappe.db.get_value('Item', {'item_code': codigo}, 'name')
            
            items.append({
                "item_code": codigo,
                "codigo_original": codigo_original,
                "item_name": descripcion[:140] if descripcion else "Sin descripción",
                "description": descripcion,
                "qty": cantidad,
                "rate": precio,
                "uom": uom,
                "exists": bool(item),
                "item_id": item if item else None
            })
            
            observaciones_items.append(f"{cantidad} {descripcion} ${precio:.2f}")
        
        # --- 6. CONSTRUIR RESPUESTA ---
        return {
            "status": "success",
            "data": {
                "tipo_dte": tipo_dte,
                "tipo_descripcion": tipo_descripcion,
                "cliente": cliente_data,
                "bill_no": codigo_generacion,
                "posting_date": fecha_emision.strftime("%Y-%m-%d") if fecha_emision else "",
                "due_date": fecha_emision.strftime("%Y-%m-%d") if fecha_emision else "",
                "dte": dte_texto,
                "items": items,
                "observaciones_items": observaciones_items,
                "observaciones_json": observaciones_json,
                "total": data.get('resumen', {}).get('totalPagar', 0),
                "subtotal": data.get('resumen', {}).get('subTotal', 0),
                "currency": data.get('identificacion', {}).get('tipoMoneda', 'USD')
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            title="Error procesando JSON Venta",
            message=f"Error: {error_msg}"
        )
        return {
            "status": "error",
            "message": f"Error interno: {error_msg}"
        }
