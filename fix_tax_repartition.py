
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def fix_tax_repartition_lines(env):
    '''
    Corregir líneas de distribución de impuestos para cumplir con validaciones de Odoo 18.0
    '''
    _logger.info("Iniciando corrección de líneas de distribución de impuestos")
    
    # Obtener todos los impuestos activos
    taxes = env['account.tax'].search([('active', '=', True)])
    
    fixed_taxes = []
    
    for tax in taxes:
        try:
            # Verificar líneas de distribución para facturas
            invoice_base_lines = tax.invoice_repartition_line_ids.filtered(
                lambda l: l.repartition_type == 'base'
            )
            
            # Verificar líneas de distribución para notas de crédito
            refund_base_lines = tax.refund_repartition_line_ids.filtered(
                lambda l: l.repartition_type == 'base'
            )
            
            needs_fix = False
            
            # Corregir líneas base para facturas
            if len(invoice_base_lines) == 0:
                _logger.info(f"Agregando línea base para facturas - Impuesto: {tax.name}")
                env['account.tax.repartition.line'].create({
                    'tax_id': tax.id,
                    'factor_percent': 100.0,
                    'repartition_type': 'base',
                    'document_type': 'invoice',
                    'sequence': 1,
                    'company_id': tax.company_id.id,
                })
                needs_fix = True
            elif len(invoice_base_lines) > 1:
                _logger.info(f"Eliminando líneas base duplicadas para facturas - Impuesto: {tax.name}")
                lines_to_delete = invoice_base_lines[1:]
                lines_to_delete.unlink()
                needs_fix = True
            
            # Corregir líneas base para notas de crédito
            if len(refund_base_lines) == 0:
                _logger.info(f"Agregando línea base para notas de crédito - Impuesto: {tax.name}")
                env['account.tax.repartition.line'].create({
                    'tax_id': tax.id,
                    'factor_percent': 100.0,
                    'repartition_type': 'base',
                    'document_type': 'refund',
                    'sequence': 1,
                    'company_id': tax.company_id.id,
                })
                needs_fix = True
            elif len(refund_base_lines) > 1:
                _logger.info(f"Eliminando líneas base duplicadas para notas de crédito - Impuesto: {tax.name}")
                lines_to_delete = refund_base_lines[1:]
                lines_to_delete.unlink()
                needs_fix = True
            
            # Asegurar que las líneas base tengan factor_percent = 100
            for line in (invoice_base_lines + refund_base_lines):
                if line.factor_percent != 100.0:
                    line.factor_percent = 100.0
                    needs_fix = True
            
            if needs_fix:
                fixed_taxes.append(tax.name)
                
        except Exception as e:
            _logger.error(f"Error procesando impuesto {tax.name}: {str(e)}")
    
    _logger.info(f"Corrección completada. Impuestos corregidos: {len(fixed_taxes)}")
    if fixed_taxes:
        _logger.info(f"Impuestos corregidos: {', '.join(fixed_taxes)}")
    
    return True

# Ejecutar la corrección
if __name__ == '__main__':
    # Este script debe ejecutarse dentro del contexto de Odoo
    pass
