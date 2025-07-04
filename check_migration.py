#!/usr/bin/env python3
"""
Script de verificación post-migración para detectar posibles problemas
"""

import os
import re
import ast
from pathlib import Path

class PostMigrationChecker:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.issues = []
        self.warnings = []
        
    def check_manifest_syntax(self, manifest_path):
        """Verificar que el manifest tenga sintaxis correcta"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Intentar parsear como Python
            ast.parse(content)
            return True
        except SyntaxError as e:
            self.issues.append(f"❌ Sintaxis incorrecta en {manifest_path}: {e}")
            return False
        except Exception as e:
            self.issues.append(f"❌ Error leyendo {manifest_path}: {e}")
            return False
    
    def check_python_syntax(self, py_file):
        """Verificar sintaxis de archivos Python"""
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            ast.parse(content)
            return True
        except SyntaxError as e:
            self.issues.append(f"❌ Sintaxis incorrecta en {py_file}: {e}")
            return False
        except Exception as e:
            self.issues.append(f"❌ Error leyendo {py_file}: {e}")
            return False
    
    def check_xml_structure(self, xml_file):
        """Verificar estructura básica de XML"""
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificaciones básicas
            if '<odoo>' not in content and '<openerp>' not in content:
                self.warnings.append(f"⚠️  {xml_file}: No contiene tag <odoo> o <openerp>")
            
            # Verificar etiquetas mal formadas
            if '</' in content and not content.count('<') == content.count('</') + content.count('/>'):
                self.warnings.append(f"⚠️  {xml_file}: Posible problema con etiquetas XML")
            
            return True
        except Exception as e:
            self.issues.append(f"❌ Error leyendo {xml_file}: {e}")
            return False
    
    def check_deprecated_patterns(self, file_path):
        """Buscar patrones obsoletos que puedan causar problemas"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            deprecated_patterns = [
                (r'from odoo\.exceptions import Warning', 'Usar UserError en lugar de Warning'),
                (r'raise Warning\(', 'Usar UserError en lugar de Warning'),
                (r'\.sudo\(\)\.write\(', 'Considerar usar .with_user() según el contexto'),
                (r'self\.pool\.get\(', 'Usar self.env[] en lugar de self.pool.get()'),
                (r'cr\.execute\(', 'Usar self.env.cr.execute()'),
                (r'openerp\.', 'Cambiar openerp por odoo'),
                (r'string="[^"]*"[^>]*>', 'Eliminar atributo string obsoleto en vistas'),
                (r'attrs="{[^}]*}"', 'Revisar uso de attrs, podría ser reemplazado por invisible='),
            ]
            
            for pattern, suggestion in deprecated_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    self.warnings.append(f"⚠️  {file_path}: {suggestion} (encontrado {len(matches)} veces)")
            
            return True
        except Exception as e:
            self.issues.append(f"❌ Error verificando {file_path}: {e}")
            return False
    
    def check_dependencies(self, module_path):
        """Verificar que las dependencias sean válidas para Odoo 18.0"""
        manifest_path = module_path / '__manifest__.py'
        
        if not manifest_path.exists():
            return False
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Dependencias obsoletas conocidas en Odoo 18.0
            obsolete_deps = [
                'website_sale_delivery',
                'website_sale_stock', 
                'stock_dropshipping',
                'account_cancel',
                'sale_margin',
                'purchase_margin',
                'account_voucher',
                'account_check_writing',
                'account_asset',
                'hr_payroll_account',
                'mrp_operations',
                'procurement',
                'stock_calendar',
            ]
            
            for dep in obsolete_deps:
                if f'"{dep}"' in content:
                    self.issues.append(f"❌ {module_path.name}: Dependencia obsoleta '{dep}'")
            
            return True
        except Exception as e:
            self.issues.append(f"❌ Error verificando dependencias de {module_path.name}: {e}")
            return False
    
    def check_module(self, module_path):
        """Verificar un módulo completo"""
        print(f"🔍 Verificando módulo: {module_path.name}")
        
        # Verificar manifest
        manifest_path = module_path / '__manifest__.py'
        if manifest_path.exists():
            self.check_manifest_syntax(manifest_path)
            self.check_dependencies(module_path)
        
        # Verificar archivos Python
        for py_file in module_path.rglob('*.py'):
            if py_file.name != '__manifest__.py':
                self.check_python_syntax(py_file)
                self.check_deprecated_patterns(py_file)
        
        # Verificar archivos XML
        for xml_file in module_path.rglob('*.xml'):
            self.check_xml_structure(xml_file)
            self.check_deprecated_patterns(xml_file)
    
    def run_checks(self):
        """Ejecutar todas las verificaciones"""
        print("🔍 Ejecutando verificaciones post-migración")
        print("=" * 50)
        
        # Encontrar módulos
        modules = []
        for item in self.base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                manifest_path = item / '__manifest__.py'
                if manifest_path.exists():
                    modules.append(item)
        
        if not modules:
            print("❌ No se encontraron módulos para verificar")
            return
        
        # Verificar cada módulo
        for module in modules:
            self.check_module(module)
        
        # Mostrar resultados
        self.show_results()
    
    def show_results(self):
        """Mostrar resultados de las verificaciones"""
        print("\n📋 RESULTADOS DE VERIFICACIÓN")
        print("=" * 50)
        
        if self.issues:
            print("\n❌ PROBLEMAS CRÍTICOS:")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n⚠️  ADVERTENCIAS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.issues and not self.warnings:
            print("✅ No se encontraron problemas críticos")
        
        print(f"\nResumen:")
        print(f"  • Problemas críticos: {len(self.issues)}")
        print(f"  • Advertencias: {len(self.warnings)}")
        
        if self.issues:
            print("\n🔧 Recomendaciones:")
            print("  • Corrige los problemas críticos antes de continuar")
            print("  • Revisa las advertencias y corrige según sea necesario")
            print("  • Ejecuta pruebas unitarias si están disponibles")

if __name__ == "__main__":
    current_dir = Path.cwd()
    checker = PostMigrationChecker(current_dir)
    checker.run_checks()
