#!/usr/bin/env python3
"""
Script para migrar módulos de Odoo 17.0 a 18.0
Basado en las mejores prácticas de migración de OCA
"""

import os
import re
import json
import subprocess
from pathlib import Path

class OdooMigrator:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.modules = []
        self.changes_log = []
        
    def find_modules(self):
        """Encontrar todos los módulos en el directorio"""
        for item in self.base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                manifest_path = item / '__manifest__.py'
                if manifest_path.exists():
                    self.modules.append(item)
                    print(f"✓ Módulo encontrado: {item.name}")
        return self.modules
    
    def update_manifest(self, module_path):
        """Actualizar el archivo __manifest__.py"""
        manifest_path = module_path / '__manifest__.py'
        
        if not manifest_path.exists():
            return False
            
        print(f"📝 Actualizando manifest: {module_path.name}")
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Actualizar versión
            old_version = re.search(r'"version"\s*:\s*"([^"]+)"', content)
            if old_version:
                old_ver = old_version.group(1)
                new_ver = re.sub(r'^17\.0\.', '18.0.', old_ver)
                content = content.replace(old_ver, new_ver)
                self.changes_log.append(f"{module_path.name}: Versión {old_ver} → {new_ver}")
            
            # Actualizar dependencias obsoletas conocidas
            deprecated_deps = {
                'website_sale_delivery': 'website_sale',
                'website_sale_stock': 'website_sale',
                'stock_dropshipping': 'stock',
                'account_cancel': 'account',
                'sale_margin': 'sale',
                'purchase_margin': 'purchase',
            }
            
            for old_dep, new_dep in deprecated_deps.items():
                if f'"{old_dep}"' in content:
                    content = content.replace(f'"{old_dep}"', f'"{new_dep}"')
                    self.changes_log.append(f"{module_path.name}: Dependencia {old_dep} → {new_dep}")
            
            # Escribir el archivo actualizado
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True
            
        except Exception as e:
            print(f"❌ Error actualizando {module_path.name}: {e}")
            return False
    
    def update_python_imports(self, module_path):
        """Actualizar imports obsoletos en archivos Python"""
        print(f"🐍 Actualizando imports Python: {module_path.name}")
        
        # Búsqueda de archivos Python
        for py_file in module_path.rglob('*.py'):
            if py_file.name in ['__init__.py', '__manifest__.py']:
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Actualizaciones comunes para Odoo 18.0
                updates = {
                    'from odoo.exceptions import Warning': 'from odoo.exceptions import UserError',
                    'from odoo.exceptions import except_orm': 'from odoo.exceptions import UserError',
                    'raise Warning(': 'raise UserError(',
                    'raise except_orm(': 'raise UserError(',
                    'from openerp import': 'from odoo import',
                    'import openerp': 'import odoo',
                    'openerp.': 'odoo.',
                    '.sudo().write(': '.with_user(self.env.user).write(',
                    'self.pool.get(': 'self.env[',
                    'self.pool[': 'self.env[',
                    'cr.execute(': 'self.env.cr.execute(',
                    'uid,': 'self.env.user.id,',
                    'context=context': 'context=self.env.context',
                }
                
                for old, new in updates.items():
                    if old in content:
                        content = content.replace(old, new)
                        self.changes_log.append(f"{py_file.relative_to(self.base_path)}: {old} → {new}")
                
                # Escribir solo si hubo cambios
                if content != original_content:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            except Exception as e:
                print(f"❌ Error procesando {py_file}: {e}")
    
    def update_xml_views(self, module_path):
        """Actualizar vistas XML"""
        print(f"📄 Actualizando vistas XML: {module_path.name}")
        
        for xml_file in module_path.rglob('*.xml'):
            try:
                with open(xml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Actualizaciones comunes para vistas XML
                updates = {
                    'tree string=': 'tree ',
                    'form string=': 'form ',
                    'search string=': 'search ',
                    'attrs=': 'invisible=',
                    'readonly="1"': 'readonly="True"',
                    'required="1"': 'required="True"',
                    'invisible="1"': 'invisible="True"',
                    'widget="email"': 'widget="email"',
                    'widget="url"': 'widget="url"',
                    'widget="phone"': 'widget="phone"',
                }
                
                for old, new in updates.items():
                    if old in content:
                        content = content.replace(old, new)
                        self.changes_log.append(f"{xml_file.relative_to(self.base_path)}: {old} → {new}")
                
                # Escribir solo si hubo cambios
                if content != original_content:
                    with open(xml_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            except Exception as e:
                print(f"❌ Error procesando {xml_file}: {e}")
    
    def update_js_files(self, module_path):
        """Actualizar archivos JavaScript"""
        print(f"🟨 Actualizando archivos JS: {module_path.name}")
        
        for js_file in module_path.rglob('*.js'):
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Actualizaciones comunes para JavaScript
                updates = {
                    'odoo.define(': 'odoo.define(',
                    'require(': 'require(',
                    'web.Widget': 'web.Widget',
                    'web.form_widgets': 'web.form_widgets',
                    'web.ListView': 'web.ListView',
                    'web.FormView': 'web.FormView',
                }
                
                for old, new in updates.items():
                    if old in content:
                        content = content.replace(old, new)
                        self.changes_log.append(f"{js_file.relative_to(self.base_path)}: {old} → {new}")
                
                # Escribir solo si hubo cambios
                if content != original_content:
                    with open(js_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            except Exception as e:
                print(f"❌ Error procesando {js_file}: {e}")
    
    def migrate_module(self, module_path):
        """Migrar un módulo completo"""
        print(f"\n🔄 Migrando módulo: {module_path.name}")
        print("=" * 50)
        
        # Actualizar manifest
        self.update_manifest(module_path)
        
        # Actualizar archivos Python
        self.update_python_imports(module_path)
        
        # Actualizar vistas XML
        self.update_xml_views(module_path)
        
        # Actualizar archivos JavaScript
        self.update_js_files(module_path)
        
        print(f"✅ Módulo {module_path.name} migrado")
    
    def migrate_all(self):
        """Migrar todos los módulos"""
        print("🚀 Iniciando migración automática a Odoo 18.0")
        print("=" * 50)
        
        # Encontrar módulos
        modules = self.find_modules()
        
        if not modules:
            print("❌ No se encontraron módulos para migrar")
            return
        
        # Migrar cada módulo
        for module in modules:
            self.migrate_module(module)
        
        # Mostrar resumen
        self.show_summary()
    
    def show_summary(self):
        """Mostrar resumen de cambios"""
        print("\n📋 RESUMEN DE CAMBIOS")
        print("=" * 50)
        
        if not self.changes_log:
            print("ℹ️  No se realizaron cambios automáticos")
            return
        
        for change in self.changes_log:
            print(f"• {change}")
        
        print(f"\n✅ Total de cambios aplicados: {len(self.changes_log)}")
        print("\n⚠️  IMPORTANTE:")
        print("   - Revisa manualmente todos los cambios")
        print("   - Ejecuta pruebas antes de usar en producción")
        print("   - Verifica dependencias y compatibilidad")

if __name__ == "__main__":
    # Directorio actual
    current_dir = Path.cwd()
    
    # Crear instancia del migrador
    migrator = OdooMigrator(current_dir)
    
    # Ejecutar migración
    migrator.migrate_all()
