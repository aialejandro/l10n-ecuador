# Notas de Migración - Ecuador EDI v18.0

## Cambios en la estructura de datos de impuestos

### Problema resuelto
Al procesar documentos EDI se presentaban errores:
1. `KeyError: 'tax_repartition_line'`
2. `KeyError: 'tax'`

### Causas
En Odoo 18.0, la estructura de datos devuelta por `_prepare_edi_tax_details()` cambió significativamente:

1. **Acceso a impuestos individuales**: En versiones anteriores se accedía al impuesto a través de:
   ```python
   tax_values["tax_repartition_line"].tax_id
   ```
   
2. **Estructura de tax_details**: Antes `tax_details` era una lista/dict directa de datos de impuestos individuales. Ahora es un dict agrupado por tax_group.

### Soluciones implementadas

#### 1. Acceso directo al impuesto
En Odoo 18.0, ahora se accede directamente al impuesto:
```python
tax_values["tax"]
```

#### 2. Iteración sobre group_tax_details
Código anterior:
```python
for tax_data in taxes_data.get("tax_details", {}).values():
    # procesar tax_data
```

Código actual:
```python
for tax_group_data in taxes_data.get("tax_details", {}).values():
    for tax_data in tax_group_data.get("group_tax_details", []):
        # procesar tax_data
```

### Archivos modificados

#### l10n_ec_account_edi/models/account_move.py
- **Método**: `filter_withholding_taxes` (línea 267)
- **Cambio**: De `tax_values["tax_repartition_line"].tax_id.tax_group_id.id` a `tax_values["tax"].tax_group_id.id`

#### l10n_ec_account_edi/models/account_edi_document.py  
- **Método**: `l10n_ec_header_get_total_with_taxes`
- **Cambio**: Iteración sobre `group_tax_details` en lugar de directamente sobre `tax_details.values()`

#### l10n_ec_account_edi/models/account_move_line.py
- **Métodos**: `_l10n_ec_get_invoice_edi_taxes` y `_l10n_ec_get_credit_note_edi_taxes`
- **Cambio**: Mismo patrón de iteración sobre `group_tax_details`

### Estructura de datos en Odoo 18.0

```python
taxes_data = {
    'tax_details': {
        'tax_group_1_id': {
            'group_tax_details': [
                {
                    'tax': tax_record,
                    'base_amount_currency': amount,
                    'tax_amount_currency': amount,
                    ...
                },
                ...
            ],
            ...
        },
        'tax_group_2_id': { ... },
        ...
    },
    'base_amount': total_base,
    'tax_amount': total_tax,
    ...
}
```

### Verificación
Todos los métodos que procesaban datos de EDI fueron actualizados para usar la nueva estructura. Los métodos `_l10n_ec_prepare_tax_vals_edi` no requieren cambios porque ya reciben el `tax_data` individual correctamente.

## Corrección de validación XSD

### Problema adicional
Después de corregir la estructura de datos de impuestos, aparecía un error de validación XSD:
```
Element 'importeTotal': This element is not expected. Expected is one of ( codDocReembolso, totalComprobantesReembolso, totalBaseImponibleReembolso, totalImpuestoReembolso, totalConImpuestos )
```

### Causa
El esquema XSD v2.1.0 requiere que ciertos elementos opcionales de reembolso aparezcan antes de `totalConImpuestos` en un orden específico.

### Solución
Se actualizó la plantilla XML `edi_invoice.xml` para incluir los elementos opcionales en el orden correcto:
1. `codDocReembolso` (opcional)
2. `totalComprobantesReembolso` (opcional)  
3. `totalBaseImponibleReembolso` (opcional)
4. `totalImpuestoReembolso` (opcional)
5. `totalConImpuestos`

También se agregaron estos campos (con valor `False`) en el diccionario de datos de la factura para mantener compatibilidad.

### Referencia
Este cambio es consistente con otros módulos de localización en Odoo 18.0 como:
- `l10n_es_edi_sii`
- `l10n_it_edi_withholding` 
- `l10n_sa_edi`

Fecha: 18 de julio de 2025
