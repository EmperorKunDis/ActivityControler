#!/bin/bash

# ╔══════════════════════════════════════════════════════════════════╗
# ║                  MacMini Activity Analyzer                        ║
# ║                    One-Click Installer                            ║
# ╔══════════════════════════════════════════════════════════════════╝

clear

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                  MacMini Activity Analyzer                        ║"
echo "║                       v1.0 - Pro Edition                          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Přejít do adresáře skriptu
cd "$(dirname "$0")"

# První spuštění - vytvoření souborů pokud neexistují
if [ ! -f "requirements.txt" ]; then
    echo "📦 První spuštění - vytvářím soubory..."
    
    # Vytvoření requirements.txt
    cat > requirements.txt << 'EOF'
pandas==2.1.4
plotly==5.18.0
python-dateutil==2.8.2
matplotlib==3.8.2
pillow==10.1.0
EOF
    
    echo "✅ requirements.txt vytvořen"
fi

# Kontrola Python3
echo ""
echo "🔍 Kontroluji Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 není nainstalován!"
    echo ""
    echo "📦 Instaluji Python3..."
    
    # Pro Apple Silicon Mac - kontrola Homebrew
    if ! command -v brew &> /dev/null; then
        echo "📦 Nejprve nainstaluji Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Přidání do PATH pro M1/M2
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    fi
    
    brew install python3
fi

echo "✅ Python3 nalezen: $(python3 --version)"

# Vytvoření virtuálního prostředí
echo ""
echo "🔧 Připravuji virtuální prostředí..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtuální prostředí vytvořeno"
fi

# Aktivace virtuálního prostředí
source venv/bin/activate

# Instalace/aktualizace závislostí
echo ""
echo "📦 Instaluji/aktualizuji závislosti..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ VŠE PŘIPRAVENO!                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Spouštím MacMini Activity Analyzer..."
echo ""

# Spuštění aplikace
python3 mac_activity_gui.py

# Po ukončení
echo ""
echo "👋 Děkujeme za použití MacMini Activity Analyzer!"
echo ""

# Deaktivace virtuálního prostředí
deactivate

# Čekání před zavřením okna
read -p "Stiskněte Enter pro ukončení..."