#!/usr/bin/env python3
"""
Script para diagnosticar y corregir problemas con impuestos en Odoo 18.0
Específicamente para el error: "Invoice and credit note distribution should each contain exactly one line for the base"
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def create_tax_fix_script():
    """Crear script SQL para corregir problemas con líneas de distribución de impuestos"""
    
    fix_script = """
-- Script para corregir problemas con líneas de distribución de impuestos
-- Odoo 18.0 requiere exactamente una línea 'base' para facturas y notas de crédito

-- 1. Identificar impuestos con problemas
SELECT 
    t.id,
    t.name,
    t.type_tax_use,
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'invoice' THEN 1 END) as base_invoice_count,
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'refund' THEN 1 END) as base_refund_count
FROM account_tax t
LEFT JOIN account_tax_repartition_line irl ON t.id = irl.tax_id
WHERE t.active = true
GROUP BY t.id, t.name, t.type_tax_use
HAVING 
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'invoice' THEN 1 END) != 1
    OR COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'refund' THEN 1 END) != 1;

-- 2. Agregar líneas base faltantes para facturas
INSERT INTO account_tax_repartition_line (
    tax_id,
    factor_percent,
    repartition_type,
    document_type,
    sequence,
    company_id
)
SELECT DISTINCT
    t.id,
    100.0,
    'base',
    'invoice',
    1,
    t.company_id
FROM account_tax t
WHERE t.active = true
AND t.id NOT IN (
    SELECT DISTINCT tax_id 
    FROM account_tax_repartition_line 
    WHERE repartition_type = 'base' 
    AND document_type = 'invoice'
    AND tax_id IS NOT NULL
);

-- 3. Agregar líneas base faltantes para notas de crédito
INSERT INTO account_tax_repartition_line (
    tax_id,
    factor_percent,
    repartition_type,
    document_type,
    sequence,
    company_id
)
SELECT DISTINCT
    t.id,
    100.0,
    'base',
    'refund',
    1,
    t.company_id
FROM account_tax t
WHERE t.active = true
AND t.id NOT IN (
    SELECT DISTINCT tax_id 
    FROM account_tax_repartition_line 
    WHERE repartition_type = 'base' 
    AND document_type = 'refund'
    AND tax_id IS NOT NULL
);

-- 4. Eliminar líneas base duplicadas (mantener solo una por tipo)
DELETE FROM account_tax_repartition_line 
WHERE id IN (
    SELECT id FROM (
        SELECT 
            id,
            ROW_NUMBER() OVER (
                PARTITION BY tax_id, repartition_type, document_type 
                ORDER BY id
            ) as rn
        FROM account_tax_repartition_line
        WHERE repartition_type = 'base'
    ) t
    WHERE t.rn > 1
);

-- 5. Asegurar que todas las líneas base tengan factor_percent = 100
UPDATE account_tax_repartition_line 
SET factor_percent = 100.0 
WHERE repartition_type = 'base' 
AND (factor_percent IS NULL OR factor_percent = 0);

-- 6. Verificar resultado final
SELECT 
    t.id,
    t.name,
    t.type_tax_use,
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'invoice' THEN 1 END) as base_invoice_count,
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'refund' THEN 1 END) as base_refund_count
FROM account_tax t
LEFT JOIN account_tax_repartition_line irl ON t.id = irl.tax_id
WHERE t.active = true
GROUP BY t.id, t.name, t.type_tax_use
HAVING 
    COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'invoice' THEN 1 END) != 1
    OR COUNT(CASE WHEN irl.repartition_type = 'base' AND irl.document_type = 'refund' THEN 1 END) != 1;
"""
    
    return fix_script

def create_odoo_tax_fixer():
    """Crear script Python para corregir impuestos usando ORM de Odoo"""
    
    fix_script = """
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
"""
    
    return fix_script

def main():
    """Función principal"""
    print("🔧 HERRAMIENTA DE CORRECCIÓN DE IMPUESTOS ODOO 18.0")
    print("=" * 60)
    print()
    print("Este script corrige el error:")
    print("'Invoice and credit note distribution should each contain exactly one line for the base'")
    print()
    
    # Crear script SQL
    sql_script = create_tax_fix_script()
    
    print("📄 Script SQL creado para corregir problemas con impuestos")
    print("=" * 50)
    
    # Guardar script SQL
    with open('fix_tax_repartition.sql', 'w') as f:
        f.write(sql_script)
    
    print("✅ Script SQL guardado como: fix_tax_repartition.sql")
    print()
    
    # Crear script Python
    python_script = create_odoo_tax_fixer()
    
    with open('fix_tax_repartition.py', 'w') as f:
        f.write(python_script)
    
    print("✅ Script Python guardado como: fix_tax_repartition.py")
    print()
    
    print("🚀 INSTRUCCIONES DE USO:")
    print("=" * 30)
    print()
    print("OPCIÓN 1 - Usando SQL (más rápido):")
    print("1. Detener Odoo")
    print("2. Ejecutar: psql -d tu_base_de_datos -f fix_tax_repartition.sql")
    print("3. Reiniciar Odoo")
    print()
    print("OPCIÓN 2 - Usando shell de Odoo:")
    print("1. python3 odoo/odoo-bin shell -d tu_base_de_datos")
    print("2. exec(open('fix_tax_repartition.py').read())")
    print("3. fix_tax_repartition_lines(env)")
    print()
    print("OPCIÓN 3 - Corregir archivo CSV y reinstalar:")
    print("1. El archivo CSV ya fue corregido")
    print("2. Desinstalar l10n_ec_base")
    print("3. Reinstalar l10n_ec_base")
    print()
    print("⚠️  IMPORTANTE: Hacer backup de la base de datos antes de ejecutar")

if __name__ == "__main__":
    main()
