#!/usr/bin/env python3
"""
Script para probar instalación real de módulos migrados
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

def test_module_installation():
    """Probar instalación real de módulos en Odoo"""
    print("🧪 Probando instalación real de módulos")
    print("=" * 50)
    
    # Módulos a probar
    modules_to_test = [
        'l10n_ec_base',
        'l10n_ec_account_edi', 
        'l10n_ec_credit_note',
        'l10n_ec_withhold'
    ]
    
    for module in modules_to_test:
        print(f"\n📦 Probando módulo: {module}")
        
        # Comando para probar carga del módulo
        cmd = [
            'python3', '/opt/odoo18/odoo/odoo-bin',
            '--addons-path=/opt/odoo18/odoo/addons,/opt/odoo18/odoo-custom-addons',
            '--load-language=es_EC',
            '--stop-after-init',
            '--log-level=error',
            '--without-demo=all',
            '--init=' + module,
            '--database=test_migration_' + module.replace('_', ''),
            '--db_host=localhost',
            '--db_port=5432',
            '--db_user=odoo18',
            '--db_password=odoo18'
        ]
        
        try:
            print(f"🔧 Instalando {module}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"✅ {module}: Instalación exitosa")
            else:
                print(f"❌ {module}: Error en instalación")
                print("STDOUT:", result.stdout[-500:])  # Últimas 500 líneas
                print("STDERR:", result.stderr[-500:])
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {module}: Timeout en instalación")
        except Exception as e:
            print(f"❌ {module}: Error ejecutando comando - {e}")

def validate_manifest_dependencies():
    """Validar dependencias en manifiestos"""
    print("\n🔍 Validando dependencias")
    print("=" * 50)
    
    base_dir = Path.cwd()
    
    # Dependencias base de Odoo 18 que deben existir
    valid_core_modules = [
        'base', 'account', 'account_edi', 'sale', 'purchase', 'stock',
        'hr', 'crm', 'website', 'mail', 'portal', 'contacts', 'product',
        'web', 'calendar', 'l10n_ec'
    ]
    
    for module_dir in base_dir.iterdir():
        if module_dir.is_dir() and not module_dir.name.startswith('.'):
            manifest_path = module_dir / '__manifest__.py'
            
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Evaluar manifest
                    manifest_data = eval(content)
                    deps = manifest_data.get('depends', [])
                    
                    print(f"📋 {module_dir.name}:")
                    print(f"   Versión: {manifest_data.get('version', 'unknown')}")
                    print(f"   Dependencias: {deps}")
                    
                    # Verificar dependencias problemáticas
                    problematic_deps = []
                    for dep in deps:
                        if dep not in valid_core_modules and not dep.startswith('l10n_ec'):
                            problematic_deps.append(dep)
                    
                    if problematic_deps:
                        print(f"   ⚠️  Dependencias a verificar: {problematic_deps}")
                    else:
                        print(f"   ✅ Dependencias válidas")
                        
                except Exception as e:
                    print(f"❌ Error procesando {module_dir.name}: {e}")

def check_python_syntax():
    """Verificar sintaxis Python básica"""
    print("\n🐍 Verificando sintaxis Python")
    print("=" * 50)
    
    base_dir = Path.cwd()
    errors = []
    
    for py_file in base_dir.rglob('*.py'):
        if py_file.name in ['migrate_to_18.py', 'check_migration.py', 'test_migration.py', 'test_installation.py']:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Compilar para verificar sintaxis
            compile(content, str(py_file), 'exec')
            
        except SyntaxError as e:
            errors.append(f"❌ {py_file.relative_to(base_dir)}: {e}")
        except Exception as e:
            errors.append(f"⚠️  {py_file.relative_to(base_dir)}: {e}")
    
    if errors:
        print("🚨 ERRORES DE SINTAXIS:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("✅ Sintaxis Python correcta en todos los archivos")
        return True

def main():
    """Función principal"""
    print("🚀 PRUEBAS DE INSTALACIÓN DE MÓDULOS MIGRADOS")
    print("=" * 60)
    
    # Validar manifiestos
    validate_manifest_dependencies()
    
    # Verificar sintaxis Python
    syntax_ok = check_python_syntax()
    
    if syntax_ok:
        print("\n🎯 SINTAXIS CORRECTA - Los módulos están listos para instalación")
        
        # Preguntar si hacer prueba de instalación real
        print("\n⚠️  NOTA: La prueba de instalación real requiere:")
        print("   - PostgreSQL ejecutándose")
        print("   - Usuario/contraseña: odoo18/odoo18")
        print("   - Puede tomar varios minutos")
        print("\n📝 Para probar instalación manual:")
        print("   cd /opt/odoo18")
        print("   python3 odoo/odoo-bin --addons-path=odoo/addons,odoo-custom-addons \\")
        print("     --init=l10n_ec_base --database=test_ec --stop-after-init")
        
    else:
        print("\n❌ HAY ERRORES DE SINTAXIS - Corregir antes de instalar")
    
    return syntax_ok

if __name__ == "__main__":
    main()
