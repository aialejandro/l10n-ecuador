
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
