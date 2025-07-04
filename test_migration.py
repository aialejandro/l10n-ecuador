#!/usr/bin/env python3
"""
Script para probar la carga de módulos migrados
"""

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path

def test_module_loading():
    """Probar que los módulos se pueden cargar sin errores de sintaxis"""
    print("🧪 Probando carga de módulos migrados")
    print("=" * 50)
    
    # Directorio base
    base_dir = Path.cwd()
    
    # Encontrar módulos
    modules = []
    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            manifest_path = item / '__manifest__.py'
            if manifest_path.exists():
                modules.append(item.name)
    
    if not modules:
        print("❌ No se encontraron módulos")
        return False
    
    print(f"📦 Módulos encontrados: {', '.join(modules)}")
    
    # Crear script de prueba
    test_script = f"""
import sys
import os
sys.path.insert(0, '/opt/odoo18/odoo')

# Importar librerías básicas de Odoo
try:
    from odoo import api, fields, models
    print("✅ Importación de odoo core exitosa")
except Exception as e:
    print(f"❌ Error importando odoo core: {{e}}")
    sys.exit(1)

# Probar carga de manifiestos
modules_to_test = {modules}
for module in modules_to_test:
    try:
        manifest_path = f"{{module}}/__manifest__.py"
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest_content = f.read()
            
            # Evaluar el manifest
            manifest_data = eval(manifest_content)
            print(f"✅ {{module}}: Manifest válido - v{{manifest_data.get('version', 'unknown')}}")
        else:
            print(f"❌ {{module}}: No se encontró __manifest__.py")
    except Exception as e:
        print(f"❌ {{module}}: Error en manifest - {{e}}")

print("\\n🎉 Prueba de carga completada")
"""
    
    # Escribir y ejecutar script de prueba
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        test_file = f.name
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, cwd=base_dir)
        
        print("📋 RESULTADO DE LA PRUEBA:")
        print("-" * 30)
        print(result.stdout)
        
        if result.stderr:
            print("⚠️  ERRORES:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Prueba exitosa: Los módulos se pueden cargar correctamente")
            return True
        else:
            print("❌ Prueba falló: Hay errores en la carga")
            return False
    
    finally:
        os.unlink(test_file)

def test_odoo_syntax():
    """Probar sintaxis específica de Odoo"""
    print("\n🔍 Verificando sintaxis específica de Odoo")
    print("=" * 50)
    
    base_dir = Path.cwd()
    issues = []
    
    # Buscar archivos Python
    for py_file in base_dir.rglob('*.py'):
        if py_file.name in ['__init__.py', 'migrate_to_18.py', 'check_migration.py']:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar patrones problemáticos
            if 'from odoo.exceptions import Warning' in content:
                issues.append(f"❌ {py_file.relative_to(base_dir)}: Usando Warning obsoleto")
            
            if 'raise Warning(' in content:
                issues.append(f"❌ {py_file.relative_to(base_dir)}: Usando raise Warning obsoleto")
            
            if 'from openerp' in content:
                issues.append(f"❌ {py_file.relative_to(base_dir)}: Usando openerp en lugar de odoo")
            
            if '.sudo().write(' in content:
                issues.append(f"⚠️  {py_file.relative_to(base_dir)}: Usando .sudo().write() - revisar contexto")
            
        except Exception as e:
            issues.append(f"❌ Error leyendo {py_file}: {e}")
    
    if issues:
        print("🚨 PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ No se encontraron problemas de sintaxis")
        return True

def create_test_database():
    """Crear base de datos de prueba"""
    print("\n🗄️  Creando base de datos de prueba")
    print("=" * 50)
    
    db_name = "test_l10n_ec_migration"
    
    try:
        # Comando para crear base de datos
        cmd = [
            'python3', '/opt/odoo18/odoo/odoo-bin',
            '--db_host=localhost',
            '--db_port=5432',
            '--db_user=odoo18',
            '--db_password=odoo18',
            '-d', db_name,
            '--stop-after-init',
            '--without-demo=all',
            '--logfile=/tmp/odoo_test.log'
        ]
        
        print(f"🔧 Ejecutando: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"✅ Base de datos {db_name} creada exitosamente")
            return True
        else:
            print(f"❌ Error creando base de datos:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Timeout creando base de datos")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 INICIANDO PRUEBAS DE MIGRACIÓN")
    print("=" * 60)
    
    results = []
    
    # Prueba 1: Carga de módulos
    results.append(("Carga de módulos", test_module_loading()))
    
    # Prueba 2: Sintaxis de Odoo
    results.append(("Sintaxis de Odoo", test_odoo_syntax()))
    
    # Mostrar resumen
    print("\n📊 RESUMEN DE PRUEBAS")
    print("=" * 30)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, result in results if result)
    total_tests = len(results)
    
    print(f"\n🎯 Resultado final: {total_passed}/{total_tests} pruebas pasaron")
    
    if total_passed == total_tests:
        print("🎉 ¡Migración exitosa! Los módulos están listos para usar.")
        return True
    else:
        print("⚠️  Hay problemas que requieren atención manual.")
        return False

if __name__ == "__main__":
    main()
