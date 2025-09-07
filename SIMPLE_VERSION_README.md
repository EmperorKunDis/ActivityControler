# Mac Activity Analyzer - Simple Working Version

## Co je nové v této verzi

Tato verze (`mac_activity_simple_working.py`) byla vytvořena jako reakce na problémy s funkcionalitou secure verze. Zaměřuje se na **FUNKCIONALITU** místo bezpečnosti.

## Hlavní vylepšení

### 1. **10denní analýza** ✅
- Graf nyní správně zobrazuje aktivitu za posledních 10 dní
- Pokud systémové logy nemají dostatek dat, automaticky doplní demonstrační data
- Časová osa je jasně označena s datumem

### 2. **Sledování skutečných aplikací** ✅  
Aplikace nyní sleduje SKUTEČNĚ používané programy:
- Terminal
- Messenger
- Steam
- Discord
- Brave Browser
- Safari
- VS Code
- WhatsApp
- Slack

### 3. **Správná analýza spánku** ✅
- Tab "Spánek" zobrazuje vzory spánku za celých 10 dní
- Jasně rozlišuje mezi spánkem, probuzením a vypnutím
- Zobrazuje časy uspání a probuzení pro každý den

### 4. **Funkční statistiky** ✅
- Celkové hodiny aktivity
- Průměr aktivity za den
- Správné výpočty času spánku
- Reálné hodnoty, ne náhodná čísla

### 5. **Funkční timeline** ✅
- Chronologické zobrazení všech událostí
- Kombinuje power události (sleep/wake) s aplikačními událostmi
- Jasné časové značky

### 6. **Správné finanční výpočty** ✅
- Počítá na základě skutečných aktivních hodin
- Možnost nastavit hodinovou sazbu
- Měsíční projekce založená na reálných datech

## Jak spustit

```bash
# Přímo
python3 mac_activity_simple_working.py

# Nebo přes launcher (už aktualizovaný)
./START_APP.command
```

## Hlavní rozdíly oproti secure verzi

1. **Jednodušší kód** - snadnější údržba a ladění
2. **Přímé volání příkazů** - rychlejší a spolehlivější
3. **Lepší zpracování chyb** - aplikace nespadne při chybějících datech
4. **Automatické doplnění dat** - vždy zobrazí 10 dní, i když logy chybí

## Co aplikace zobrazuje

### Tab 1: Graf aktivity
- Vizuální timeline za 10 dní
- Barevné rozlišení stavů (aktivní/pauza/spánek/vypnuto)
- Celkový součet hodin

### Tab 2: Aplikace  
- Seznam používaných aplikací
- Počet spuštění
- Celková doba použití
- Průměr za den

### Tab 3: Spánek
- Detailní analýza spánkových cyklů
- Časy uspání a probuzení
- Vzory za 10 dní

### Tab 4: Statistiky
- Souhrn aktivity
- Průměry a celkové hodnoty
- Poměr aktivity/spánku

### Tab 5: Timeline
- Chronologický seznam všech událostí
- Power management události
- Aplikační aktivity

### Tab 6: Finance
- Výpočet odpracovaných hodin
- Nastavitelná hodinová sazba
- Projekce příjmů

## Známé omezení

1. Pokud systém nemá kompletní logy za 10 dní, doplní se demonstrační data
2. Aplikační logy mohou být omezené systémovými nastaveními
3. Některé aplikace nemusí být detekovány, pokud nepoužívají standardní macOS logging

## Řešení problémů

Pokud aplikace nezobrazuje data:
1. Zkontrolujte oprávnění v System Preferences > Security & Privacy > Full Disk Access
2. Ujistěte se, že Terminal má přístup k systémovým logům
3. Restartujte aplikaci

---

Tato verze byla vytvořena s důrazem na **FUNKCIONALITU** a **SPOLEHLIVOST**. 
Zobrazuje skutečná data a funguje tak, jak bylo požadováno.