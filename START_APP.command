#!/usr/bin/env bash

# Mac Activity Analyzer - Advanced Version
# Automatický spouštěč s instalací závislostí

echo "🔧 Nastavuji oprávnění..."
chmod +x "$0"
chmod +x /Users/martinsvanda/Prace/ActivityControler/START_APP.command

echo "🚀 Spouštím Mac Activity Analyzer - Advanced Version..."

# Získat adresář skriptu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Kontrola Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 není nainstalován!"
    echo "Nainstalujte ho příkazem: brew install python3"
    exit 1
fi

# Vytvoření virtuálního prostředí pokud neexistuje
if [ ! -d "venv" ]; then
    echo "📦 Vytvářím virtuální prostředí..."
    python3 -m venv venv
fi

# Aktivace virtuálního prostředí
source venv/bin/activate

# Instalace závislostí
if [ ! -f ".deps_installed" ]; then
    echo "📦 Instaluji závislosti (pouze při prvním spuštění)..."
    pip install --upgrade pip --quiet
    pip install pandas matplotlib --quiet
    touch .deps_installed
fi

# Spuštění aplikace
echo "🥦 Spouštím aplikaci..."
# Choose which version to run:
# python3 mac_activity_advanced.py  # Original version
# python3 mac_activity_advanced_secure.py  # Secure version with all protections
python mac_activity_simple_working.py  # Simple working version - FUNCTIONAL!

# Deactivate virtual environment
deactivate