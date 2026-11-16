frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        if (!frm.is_new()) return;

        frm.remove_custom_button(__('Importar desde JSON'), __('Importar'));

        frm.add_custom_button(__('Importar desde JSON'), function() {
            let input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';

            input.onchange = function(e) {
                let file = e.target.files[0];
                if (!file) return;

                let reader = new FileReader();
                
                reader.onload = function(evt) {
                    try {
                        let jsonContent = evt.target.result;
                        let jsonData = JSON.parse(jsonContent);
                        
                        if (!jsonData.identificacion || !jsonData.emisor) {
                            frappe.msgprint({
                                title: __('Error en archivo'),
                                message: `El archivo "${file.name}" no tiene la estructura esperada.`,
                                indicator: 'red'
                            });
                            return;
                        }

                        frappe.show_alert({
                            message: __('Procesando archivo: {0}', [file.name]),
                            indicator: 'blue'
                        });

                        frappe.call({
                            method: 'corad_custom.personalizaciones.api.obtener_datos_json',
                            args: { 
                                'data': jsonContent 
                            },
                            callback: function(response) {
                                if (response.message && response.message.status === 'success') {
                                    let data = response.message.data;
                                    
                                    // --- Mostrar tipo detectado ---
                                    let tipoMsg = data.es_sujeto_excluido ? '🟡 Sujeto Excluido (SE)' : '🔵 Factura de Compra (CCF)';
                                    frappe.show_alert({
                                        message: __('Tipo detectado: {0} - {1}', [tipoMsg, data.tipo_descripcion]),
                                        indicator: 'blue'
                                    });
                                    
                                    // --- 1. PROVEEDOR ---
                                    if (data.supplier) {
                                        if (data.supplier.exists) {
                                            frm.set_value('supplier', data.supplier.name);
                                            frappe.show_alert({
                                                message: __('✅ Proveedor encontrado: {0}', [data.supplier.supplier_name]),
                                                indicator: 'green'
                                            });
                                        } else {
                                            let mensaje = __('El proveedor "{0}" no existe en el sistema.\nNIT: {1}\nTipo: {2}', 
                                                [data.supplier.supplier_name, data.supplier.tax_id, data.supplier.tipo]);
                                            mensaje += '\n\n' + __('¿Deseas crearlo ahora?');
                                            
                                            frappe.confirm(
                                                mensaje,
                                                function() {
                                                    frappe.call({
                                                        method: 'frappe.client.insert',
                                                        args: {
                                                            doc: {
                                                                doctype: 'Supplier',
                                                                supplier_name: data.supplier.supplier_name,
                                                                supplier_group: 'Proveedores',
                                                                tax_id: data.supplier.tax_id,
                                                                country: 'El Salvador',
                                                                default_currency: 'USD'
                                                            }
                                                        },
                                                        callback: function(r) {
                                                            if (r.message) {
                                                                frm.set_value('supplier', r.message.name);
                                                                frappe.show_alert({
                                                                    message: __('✅ Proveedor creado: {0}', [r.message.name]),
                                                                    indicator: 'green'
                                                                });
                                                            }
                                                        }
                                                    });
                                                },
                                                function() {
                                                    frappe.show_alert({
                                                        message: __('⚠️ Proveedor no creado. Selecciona uno manualmente.'),
                                                        indicator: 'orange'
                                                    });
                                                }
                                            );
                                        }
                                    }
                                    
                                    // --- 2. DATOS FACTURA ---
                                    if (data.bill_no) frm.set_value('bill_no', data.bill_no);
                                    if (data.bill_date) frm.set_value('bill_date', data.bill_date);
                                    if (data.posting_date) frm.set_value('posting_date', data.posting_date);
                                    if (data.due_date) frm.set_value('due_date', data.due_date);
                                    
                                    // --- 3. DTE EN custom_dte ---
                                    if (data.dte) {
                                        frm.set_value('custom_dte', data.dte);
                                    }
                                    
                                    // --- 4. ITEMS EN TABLA ---
                                    if (data.items && data.items.length > 0) {
                                        frm.clear_table('items');
                                        
                                        data.items.forEach(function(item) {
                                            let row = frm.add_child('items');
                                            row.item_code = item.item_code;
                                            row.item_name = item.item_name;
                                            row.description = item.description;
                                            row.qty = item.qty;
                                            row.rate = item.rate;
                                            row.uom = item.uom;
                                            row.conversion_factor = 1;
                                            
                                            if (item.exists) {
                                                row.item_code = item.item_id;
                                            } else {
                                                frappe.call({
                                                    method: 'frappe.client.insert',
                                                    args: {
                                                        doc: {
                                                            doctype: 'Item',
                                                            item_code: item.item_code,
                                                            item_name: item.item_name,
                                                            description: item.description,
                                                            item_group: 'Productos',
                                                            stock_uom: item.uom,
                                                            is_stock_item: 1,
                                                            standard_rate: item.rate
                                                        }
                                                    },
                                                    callback: function(r) {
                                                        if (r.message) {
                                                            row.item_code = r.message.name;
                                                            frm.refresh_field('items');
                                                            frappe.show_alert({
                                                                message: __('✅ Item creado: {0}', [r.message.name]),
                                                                indicator: 'green'
                                                            });
                                                        }
                                                    }
                                                });
                                            }
                                        });
                                        
                                        frm.refresh_field('items');
                                    }
                                    
                                    // --- 5. OBSERVACIONES ---
                                    let observaciones_final = [];
                                    
                                    // 5a. Agregar observaciones de items
                                    if (data.observaciones_items && data.observaciones_items.length > 0) {
                                        observaciones_final.push(data.observaciones_items.join('\n'));
                                    }
                                    
                                    // 5b. Agregar observaciones del JSON (si existe)
                                    if (data.observaciones_json) {
                                        observaciones_final.push('📝 ' + data.observaciones_json);
                                    }
                                    
                                    // 5c. Agregar información del tipo de factura
                                    let tipoLabel = data.es_sujeto_excluido ? 'Sujeto Excluido' : 'Factura de Compra';
                                    observaciones_final.push('📄 Tipo: ' + tipoLabel + ' (' + data.tipo_dte + ' - ' + data.tipo_descripcion + ')');
                                    
                                    // Unir todo en el campo remarks
                                    if (observaciones_final.length > 0) {
                                        frm.set_value('remarks', observaciones_final.join('\n\n'));
                                    }
                                    
                                    // --- 6. MENSAJE FINAL ---
                                    let estado = data.supplier.exists ? '✅ Encontrado' : '❌ No existe (se creará)';
                                    let tipoDetectado = data.es_sujeto_excluido ? 'Sujeto Excluido (SE)' : 'Factura de Compra (CCF)';
                                    
                                    frappe.msgprint({
                                        title: __('✅ Datos importados'),
                                        message: __('Tipo: {0} ({1})\n'
                                            + 'Proveedor: {2} - {3}\n'
                                            + 'Factura No.: {4}\n'
                                            + 'Items: {5}\n\n'
                                            + '📌 Revisa y guarda el borrador.', 
                                            [tipoDetectado, data.tipo_descripcion, data.supplier.supplier_name, estado, data.bill_no, data.items.length]),
                                        indicator: 'green'
                                    });
                                    
                                    frm.dirty();
                                    
                                } else {
                                    frappe.msgprint({
                                        title: __('Error'),
                                        message: response.message.message || 'Error al procesar el JSON.',
                                        indicator: 'red'
                                    });
                                }
                            },
                            error: function(error) {
                                frappe.msgprint({
                                    title: __('Error'),
                                    message: 'Error al comunicarse con el servidor.',
                                    indicator: 'red'
                                });
                                console.error("Error:", error);
                            }
                        });
                    } catch (error) {
                        frappe.msgprint({
                            title: __('Error en archivo'),
                            message: `El archivo "${file.name}" no es un JSON válido.`,
                            indicator: 'red'
                        });
                    }
                };
                
                reader.readAsText(file);
            };

            input.click();
        }, __('Importar'));
    }
});
