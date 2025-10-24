# TXT Files Examples
# SRI Document Access Keys for Import Testing

## 📋 Purpose
This folder contains example TXT files with SRI document access keys. Each file demonstrates different scenarios and document types that the Ecuador EDI Import module should handle.

## 📝 File Format Specification

### TXT File Structure
```
# Each line contains a 49-character SRI document access key
0210202408090990032319001210010020000001238011823147
0410202408090990032319001210010020000000458096541237
0710202408150990032319001210010020000000128043567891
```

### Access Key Format Breakdown
```
Position:  0123456789012345678901234567890123456789012345678
Example:   0210202408090990032319001210010020000001238011823147
           ^^  ^^^^^^ ^^^^^^^^^^^^^ ^^ ^^ ^^^ ^^^^^^^^^ ^^^^^^^^ ^ ^
           ||  ||||||  ||||||||||| || || ||| |||||||||  |||||||| | |
           ||  ||||||  ||||||||||| || || ||| |||||||||  |||||||| | +-- Verification digit
           ||  ||||||  ||||||||||| || || ||| |||||||||  |||||||| +---- Emission type (1=normal, 2=contingency)  
           ||  ||||||  ||||||||||| || || ||| |||||||||  +------------- Numeric code (8 digits)
           ||  ||||||  ||||||||||| || || ||| +----------------------- Sequential number (9 digits)
           ||  ||||||  ||||||||||| || || +---------------------------- Point of sale (3 digits)
           ||  ||||||  ||||||||||| || +------------------------------- Establishment (2 digits)
           ||  ||||||  ||||||||||| +---------------------------------- Environment code (2 digits)
           ||  ||||||  +---------------------------------------------- RUC/Tax ID (13 digits)
           ||  +---------------------------------------------------- Issue date (DDMMYY)
           +------------------------------------------------------- Document type + Environment
```

### Document Type Codes
- `01` - Factura Electrónica (Electronic Invoice)
- `04` - Nota de Crédito Electrónica (Electronic Credit Note)  
- `05` - Nota de Débito Electrónica (Electronic Debit Note)
- `06` - Guía de Remisión Electrónica (Electronic Delivery Note)
- `07` - Comprobante de Retención Electrónica (Electronic Withholding Receipt)

### Environment Codes
- `01` - Test/Development environment
- `02` - Production environment

## 📁 Recommended File Organization

### By Document Type
```
invoices_20240809.txt          # Only invoice access keys
credit_notes_20240809.txt      # Only credit note access keys  
debit_notes_20240809.txt       # Only debit note access keys
delivery_notes_20240809.txt    # Only delivery note access keys
withholdings_20240815.txt      # Only withholding access keys
```

### By Date Range
```
documents_20240801_20240807.txt    # Week 1 of August 2024
documents_20240808_20240814.txt    # Week 2 of August 2024
documents_20240815_20240821.txt    # Week 3 of August 2024
```

### By Processing Scenario
```
valid_documents.txt            # All valid access keys
mixed_types.txt               # Mix of different document types
test_environment.txt          # Documents from test environment
production_environment.txt    # Documents from production environment
error_scenarios.txt          # Keys that should trigger specific errors
```

## 🧪 Testing Scenarios

### Scenario 1: Single Document Type
**File**: `invoices_sample.txt`
```
# Sample invoice access keys
0210202408090990032319001210010020000001238011823147
0210202408090990032319001210010020000001248011823158  
0210202408090990032319001210010020000001258011823169
```

### Scenario 2: Mixed Document Types
**File**: `mixed_documents.txt`
```
# Mixed document types in single file
0210202408090990032319001210010020000001238011823147  # Invoice
0410202408090990032319001210010020000000458096541237  # Credit Note
0710202408150990032319001210010020000000128043567891  # Withholding
```

### Scenario 3: Error Handling
**File**: `error_scenarios.txt`
```
# Invalid access keys for error testing
0210202408090990032319001210010020000001238011823148  # Wrong verification digit
021020240809099003231900121001002000000123801182314   # Too short (48 chars)
0210202408090990032319001210010020000001238011823147X # Too long (50 chars)
```

## ⚠️ Important Notes

### File Requirements
- **Encoding**: UTF-8 or ISO-8859-1
- **Line Endings**: Unix (LF) or Windows (CRLF) 
- **Max File Size**: 5 MB
- **Max Lines**: Approximately 100,000 access keys per file

### Access Key Validation
- Must be exactly 49 characters
- All characters must be numeric
- Verification digit must be correct
- Date must be valid (positions 4-9)
- RUC must be valid Ecuador tax ID format

### Processing Expectations
When the module processes these TXT files:
1. Each line will be parsed as an access key
2. Invalid lines will be logged but won't stop processing
3. Valid keys will trigger SRI web service calls
4. Retrieved XMLs will be validated and processed
5. Resulting documents will be created in Odoo

## 🎯 Place Your TXT Files Here

**Instructions for adding your TXT files:**

1. **Copy your TXT files** to this folder
2. **Use descriptive names** following the conventions above
3. **Verify file encoding** is UTF-8 or ISO-8859-1
4. **Test with small files first** (10-20 access keys)
5. **Document any special scenarios** in file comments

### Example File Placement
```
/docs/examples/sample_files/txt_files/
├── your_invoices_20240821.txt
├── your_withholdings_20240821.txt  
├── your_mixed_documents.txt
└── your_test_scenarios.txt
```

The module's import wizard will be able to process any TXT files you place in this folder, making them perfect for testing and development.
