#!/usr/bin/env python3
"""
Přímý spouštěč aplikace - obchází problémy s oprávněními .command souborů
Spusťte: python3 run_app.py
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🚀 MacMini Activity Analyzer - Launcher")
    print("=" * 50)
    
    # Kontrola že jsme na macOS
    if sys.platform != "darwin":
        print("❌ Tato aplikace je určena pouze pro macOS!")
        sys.exit(1)
    
    # Instalace požadavků
    print("\n📦 Kontroluji a instaluji závislosti...")
    
    required_packages = [
        'pandas',
        'matplotlib', 
        'pillow',
        'python-dateutil'
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} - již nainstalováno")
        except ImportError:
            print(f"📥 Instaluji {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
    
    print("\n✅ Všechny závislosti jsou připraveny!")
    print("\n🎯 Spouštím hlavní aplikaci...\n")
    print("=" * 50)
    
    # Spuštění hlavní aplikace
    try:
        # Importovat a spustit hlavní aplikaci
        import mac_activity_gui
        import tkinter as tk
        
        root = tk.Tk()
        app = mac_activity_gui.MacActivityGUI(root)
        root.mainloop()
        
    except Exception as e:
        print(f"\n❌ Chyba při spuštění aplikace: {e}")
        print("\nZkuste spustit přímo: python3 mac_activity_gui.py")
        sys.exit(1)

if __name__ == "__main__":
    main()