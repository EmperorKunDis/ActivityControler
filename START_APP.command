#!/usr/bin/env bash

# Alternativní spouštěč který sám nastaví oprávnění

echo "🔧 Nastavuji oprávnění..."
chmod +x "$0"

echo "🚀 Spouštím MacMini Activity Analyzer..."

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
    pip install pandas matplotlib pillow python-dateutil --quiet
    touch .deps_installed
fi

# Spuštění aplikace
python3 mac_activity_gui.py

# Deaktivace
deactivate