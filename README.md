# MacMini Activity Analyzer 💻

## Profesionální nástroj pro analýzu aktivity Mac počítače s finančním přehledem

### 🚀 Rychlý start - DVA KLIKY!

1. **Stáhněte všechny soubory** do jedné složky:
   - `run.command`
   - `mac_activity_gui.py`
   - `requirements.txt`

2. **Dvojklik na `run.command`**
   - Při prvním spuštění povolte v Nastavení → Soukromí a zabezpečení
   - Automaticky se nainstaluje vše potřebné
   - Aplikace se sama spustí

### ✨ Funkce

#### 📊 Vizualizace aktivity
- **Interaktivní graf** s barevným kódováním:
  - 🟩 Zelená = Aktivní práce (<60 sekund nečinnosti)
  - 🔴 Červená = Pauza (>60 sekund nečinnosti)
  - ⚪ Šedá = Spánek počítače
  - ⚫ Černá = Vypnutý počítač

#### 💰 Finanční přehled
- Automatický výpočet odměny (výchozí: 40h = 10 000 Kč)
- Nastavitelná hodinová sazba
- Týdenní a měsíční projekce
- Export do HTML reportu

#### 📈 Statistiky
- Denní přehled aktivity
- Celkový souhrn za 10 dní
- Efektivita práce v procentech
- Raw data log pro technickou analýzu

### 🖱️ Interaktivní ovládání

**Kliknutí na graf:**
- Zobrazí detailní informace o vybraném úseku
- Ukáže přesný čas začátku a konce
- Vypočítá finanční hodnotu úseku
- Zobrazí původní systémové logy

### 📁 Struktura souborů

```
mac-activity-analyzer/
│
├── run.command           # Spouštěč (dvojklik pro start)
├── mac_activity_gui.py   # Hlavní aplikace
├── requirements.txt      # Python závislosti
└── README.md            # Tento soubor
```

### 🛠️ Požadavky

- **macOS** (testováno na Mac s M1/M2/M3)
- **Python 3.8+** (automaticky nainstaluje)
- **5 MB** volného místa

### 📊 Výstupy

1. **Interaktivní GUI** s 4 taby:
   - Graf aktivity
   - Statistiky
   - Finanční přehled
   - Raw data

2. **HTML Report** s kompletním přehledem
   - Finanční souhrn
   - Detailní tabulka aktivit
   - Exportovatelný a sdílený

### 🔧 Řešení problémů

**"run.command nelze otevřít"**
```bash
chmod +x run.command
```

**"Python nenalezen"**
- Script automaticky nainstaluje Python přes Homebrew

**"Žádná data"**
- Ujistěte se, že Mac běží alespoň několik hodin
- Zkontrolujte oprávnění pro Terminal

### 🎯 Pro firemní použití

Ideální pro:
- Sledování využití služebních počítačů
- Fakturaci podle odpracovaných hodin
- Analýzu produktivity
- Reporting pro management

### 📝 Poznámky

- Analyzuje posledních 10 dní
- Data jsou čtena ze systémových logů
- Žádné sledování v reálném čase
- Respektuje soukromí - nesleduje obsah práce

### 🆘 Podpora

Při problémech zkontrolujte:
1. macOS je aktuální
2. Terminal má oprávnění (Nastavení → Soukromí)
3. Složka není v iCloud (lokální disk)

---

**Verze:** 1.0  
**Kompatibilita:** macOS 11+ (Big Sur a novější)  
**Optimalizováno pro:** Apple Silicon (M1/M2/M3)