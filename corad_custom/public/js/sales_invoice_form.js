frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            return;
        }

        frm.remove_custom_button(__('Importar desde JSON'), __('Importar'));

        frm.add_custom_button(__('Importar desde JSON'), function() {
            let input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.multiple = true;

            input.onchange = function(e) {
                let files = e.target.files;
                if (!files || files.length === 0) return;

                for (let i = 0; i < files.length; i++) {
                    let file = files[i];
                    let reader = new FileReader();
                    
                    reader.onload = function(evt) {
                        try {
                            let jsonContent = evt.target.result;
                            let jsonData = JSON.parse(jsonContent);
                            
                            if (!jsonData.identificacion || !jsonData.emisor || !jsonData.receptor) {
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
                                method: 'corad_custom.personalizaciones.api.obtener_datos_json_venta',
                                args: { 
                                    'data': jsonContent 
                                },
                                freeze: true,
                                freeze_message: __('Procesando factura de venta...'),
                                callback: function(response) {
                                    if (response.message && response.message.status === 'success') {
                                        let data = response.message.data;
                                        let nombre_cliente = '';
                                        let sucursal = '';
                                        
                                        // --- 1. CLIENTE ---
                                        if (data.cliente) {
                                            if (data.cliente.exists) {
                                                frm.set_value('customer', data.cliente.name);
                                                nombre_cliente = data.cliente.customer_name;
                                                frappe.show_alert({
                                                    message: __('✅ Cliente encontrado: {0}', [nombre_cliente]),
                                                    indicator: 'green'
                                                });
                                            } else {
                                                let mensaje = __('El cliente "{0}" no existe en el sistema.', 
                                                    [data.cliente.customer_name]);
                                                mensaje += '\n\n' + __('Por favor, crea el cliente manualmente antes de importar la factura.');
                                                frappe.msgprint({
                                                    title: __('⚠️ Cliente no encontrado'),
                                                    message: mensaje,
                                                    indicator: 'orange'
                                                });
                                            }
                                        }
                                        
                                        // --- 2. EXTRAER SUCURSAL ---
                                        if (nombre_cliente) {
                                            let match = nombre_cliente.match(/Punto de venta\s+([A-Za-z0-9]+)/i);
                                            if (match) {
                                                sucursal = match[1];
                                            }
                                        }
                                        
                                        // --- 3. ASIGNAR CAMPOS SEGÚN SUCURSAL ---
                                        if (sucursal) {
                                            // 3a. Centro de costos
                                            if (frm.fields_dict.cost_center) {
                                                frappe.call({
                                                    method: 'frappe.client.get_list',
                                                    args: {
                                                        doctype: 'Cost Center',
                                                        filters: {
                                                            'cost_center_name': sucursal,
                                                            'is_group': 0
                                                        },
                                                        fields: ['name'],
                                                        limit: 1
                                                    },
                                                    callback: function(r) {
                                                        if (r.message && r.message.length > 0) {
                                                            frm.set_value('cost_center', r.message[0].name);
                                                            frappe.show_alert({
                                                                message: __('✅ Centro de costos: {0}', [sucursal]),
                                                                indicator: 'green'
                                                            });
                                                        } else {
                                                            frappe.show_alert({
                                                                message: __('⚠️ Centro de costos "{0}" no encontrado', [sucursal]),
                                                                indicator: 'orange'
                                                            });
                                                        }
                                                    }
                                                });
                                            }
                                            
                                            // 3b. Incluir Pago (POS) - ACTIVADO
                                            if (frm.fields_dict.is_pos) {
                                                frm.set_value('is_pos', 1);
                                                frappe.show_alert({
                                                    message: __('✅ POS activado'),
                                                    indicator: 'green'
                                                });
                                            }
                                            // 3c. Perfil de POS
                                            if (frm.fields_dict.pos_profile) {
                                                frappe.call({
                                                    method: 'frappe.client.get_list',
                                                    args: {
                                                        doctype: 'POS Profile',
                                                        filters: {
                                                            'name': ['like', '%' + sucursal + '%']
                                                        },
                                                        fields: ['name'],
                                                        limit: 1
                                                    },
                                                    callback: function(r) {
                                                        if (r.message && r.message.length > 0) {
                                                            frm.set_value('pos_profile', r.message[0].name);
                                                            frappe.show_alert({
                                                                message: __('✅ Perfil POS: {0}', [r.message[0].name]),
                                                                indicator: 'green'
                                                            });
                                                        } else {
                                                            frappe.show_alert({
                                                                message: __('⚠️ Perfil POS "{0}" no encontrado', [sucursal]),
                                                                indicator: 'orange'
                                                            });
                                                        }
                                                    }
                                                });
                                            }
                                            
                                            // 3d. Almacén de origen
                                            if (frm.fields_dict.set_warehouse) {
                                                frappe.call({
                                                    method: 'frappe.client.get_list',
                                                    args: {
                                                        doctype: 'Warehouse',
                                                        filters: {
                                                            'warehouse_name': ['like', '%' + sucursal + '%'],
                                                            'is_group': 0
                                                        },
                                                        fields: ['name'],
                                                        limit: 1
                                                    },
                                                    callback: function(r) {
                                                        if (r.message && r.message.length > 0) {
                                                            frm.set_value('set_warehouse', r.message[0].name);
                                                            frappe.show_alert({
                                                                message: __('✅ Almacén: {0}', [r.message[0].name]),
                                                                indicator: 'green'
                                                            });
                                                        } else {
                                                            frappe.show_alert({
                                                                message: __('⚠️ Almacén "{0}" no encontrado', [sucursal]),
                                                                indicator: 'orange'
                                                            });
                                                        }
                                                    }
                                                });
                                            }
                                        }
                                        
                                        // --- 4. FECHAS ---
                                        if (data.posting_date) {
                                            frm.set_value('posting_date', data.posting_date);
                                        }
                                        
                                        if (data.due_date) {
                                            frm.set_value('due_date', data.due_date);
                                        }
                                        
                                        // --- 5. DTE ---
                                        if (data.dte) {
                                            if (frm.fields_dict.custom_dte) {
                                                frm.set_value('custom_dte', data.dte);
                                            } else {
                                                let current_remarks = frm.doc.remarks || '';
                                                frm.set_value('remarks', current_remarks ? current_remarks + '\n\n' + data.dte : data.dte);
                                            }
                                        }
                                        
                                        // --- 6. ITEMS ---
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
                                            frappe.show_alert({
                                                message: __('✅ {0} items cargados', [data.items.length]),
                                                indicator: 'green'
                                            });
                                        }
                                        
                                        // --- 7. OBSERVACIONES ---
                                        let observaciones_final = [];
                                        
                                        if (data.observaciones_items && data.observaciones_items.length > 0) {
                                            observaciones_final.push(data.observaciones_items.join('\n'));
                                        }
                                        
                                        if (data.observaciones_json) {
                                            observaciones_final.push('📝 ' + data.observaciones_json);
                                        }
                                        
                                        let tipoLabel = 'Factura de Venta';
                                        observaciones_final.push('📄 Tipo: ' + tipoLabel + ' (' + data.tipo_dte + ' - ' + data.tipo_descripcion + ')');
                                        
                                        if (sucursal) {
                                            observaciones_final.push('🏪 Sucursal: ' + sucursal);
                                        }
                                        
                                        if (observaciones_final.length > 0) {
                                            let current_remarks = frm.doc.remarks || '';
                                            if (current_remarks) {
                                                frm.set_value('remarks', current_remarks + '\n\n' + observaciones_final.join('\n\n'));
                                            } else {
                                                frm.set_value('remarks', observaciones_final.join('\n\n'));
                                            }
                                        }
                                        
                                        // --- 8. MENSAJE FINAL ---
                                        let estadoCliente = data.cliente.exists ? '✅ Encontrado' : '❌ No existe';
                                        let clienteNombre = data.cliente.customer_name || 'No disponible';
                                        
                                        let mensajeFinal = __('Tipo: {0} ({1})\n'
                                            + 'Cliente: {2} - {3}\n'
                                            + 'Items cargados: {4}', 
                                            ['Factura de Venta', data.tipo_descripcion, clienteNombre, estadoCliente, data.items ? data.items.length : 0]);
                                        
                                        if (sucursal) {
                                            mensajeFinal += '\n🏪 Sucursal detectada: ' + sucursal;
                                        }
                                        
                                        frappe.msgprint({
                                            title: __('✅ Datos importados correctamente'),
                                            message: mensajeFinal,
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
                }
            };

            input.click();
        }, __('Importar'));
    }
});
