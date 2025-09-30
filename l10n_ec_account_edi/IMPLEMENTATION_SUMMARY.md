# Implementación de Guardado de XML EDI en el Chatter

## Problema identificado
Al revisar el código del módulo EDI de Ecuador (`l10n_ec_account_edi`), se encontró que aunque el XML se estaba generando correctamente y guardando como attachment en el documento EDI, no se estaba posteando automáticamente en el chatter de la factura.

## Análisis del flujo
1. El módulo EDI de Ecuador genera el XML usando `_l10n_ec_render_xml_edi()`
2. El XML se firma usando `action_sign()`
3. Se crea un attachment con el XML firmado
4. El attachment se asigna al documento EDI (`edi_doc.attachment_id`)
5. **FALTABA**: Postear el attachment en el chatter de la factura

## Solución implementada
Se modificó el archivo `/opt/odoo18/odoo-custom-addons/l10n-ecuador/l10n_ec_account_edi/models/account_edi_format.py` en la función `_l10n_ec_post_invoice_edi()`.

### Código agregado (líneas 323-327):
```python
# Si el documento se generó exitosamente, agregarlo al chatter
if attachment and not errors and is_auth:
    document.with_context(no_new_invoice=True).message_post(
        body=_("Documento EDI generado exitosamente: %s") % edi_doc._l10n_ec_get_edi_name(),
        attachment_ids=[attachment.id]
    )
```

### Lógica de la implementación:
- **Condición**: Solo se ejecuta si hay un attachment, no hay errores y el documento está autorizado
- **Contexto**: Se usa `no_new_invoice=True` para evitar efectos secundarios
- **Mensaje**: Se incluye el nombre del documento EDI para identificación
- **Attachment**: Se adjunta el XML al mensaje del chatter

## Beneficios
1. **Trazabilidad**: El XML EDI queda visible en el historial de la factura
2. **Accesibilidad**: Los usuarios pueden descargar el XML directamente desde el chatter
3. **Auditoria**: Queda registro de cuándo se generó el documento EDI
4. **Compatibilidad**: No interfiere con el flujo existente del EDI

## Para probar la funcionalidad
1. Crear una factura con formato EDI de Ecuador configurado
2. Procesar el documento EDI
3. Verificar en el chatter que aparece el mensaje: "Documento EDI generado exitosamente: [nombre]"
4. Confirmar que el archivo XML está adjunto y se puede descargar

## Archivos modificados
- `/opt/odoo18/odoo-custom-addons/l10n-ecuador/l10n_ec_account_edi/models/account_edi_format.py`
