#!/usr/bin/env python3
"""
Configuration Manager Module

Centralizovaná správa konfigurace s validací, persistence a notifikacemi změn.
Implementuje type-safe přístup ke konfiguraci s automatickým ukládáním.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime
from dataclasses import dataclass, asdict
import copy


@dataclass
class ConfigSchema:
    """
    Schema konfigurace s výchozími hodnotami
    
    @description Definuje strukturu a validační pravidla konfigurace
    """
    # Analýza
    analysis_retention_days: int = 10
    analysis_hourly_rate: float = 250.0
    analysis_inactivity_threshold: int = 60
    analysis_max_events: int = 10000
    
    # Výkon
    performance_thread_pool_size: int = 4
    performance_command_timeout: int = 30
    performance_cache_ttl: int = 300
    performance_max_memory_mb: int = 500
    
    # UI
    ui_refresh_interval: int = 1000
    ui_max_graph_points: int = 1000
    ui_default_theme: str = 'light'
    ui_language: str = 'cs'
    
    # Bezpečnost
    security_enable_logging: bool = True
    security_log_retention_days: int = 7
    security_max_log_size_mb: int = 100
    
    # Cesty
    paths_data_dir: str = ""
    paths_log_dir: str = ""
    paths_export_dir: str = ""
    
    def validate(self) -> List[str]:
        """
        Validuje hodnoty konfigurace
        
        @returns: Seznam chybových zpráv (prázdný pokud je vše OK)
        """
        errors = []
        
        # Validace číselných hodnot
        if self.analysis_retention_days < 1 or self.analysis_retention_days > 365:
            errors.append("analysis_retention_days musí být mezi 1 a 365")
        
        if self.analysis_hourly_rate < 0:
            errors.append("analysis_hourly_rate nemůže být záporná")
        
        if self.analysis_inactivity_threshold < 10 or self.analysis_inactivity_threshold > 3600:
            errors.append("analysis_inactivity_threshold musí být mezi 10 a 3600 sekund")
        
        if self.performance_thread_pool_size < 1 or self.performance_thread_pool_size > 16:
            errors.append("performance_thread_pool_size musí být mezi 1 a 16")
        
        if self.ui_refresh_interval < 100 or self.ui_refresh_interval > 60000:
            errors.append("ui_refresh_interval musí být mezi 100 a 60000 ms")
        
        # Validace stringů
        if self.ui_default_theme not in ['light', 'dark']:
            errors.append("ui_default_theme musí být 'light' nebo 'dark'")
        
        if self.ui_language not in ['cs', 'en']:
            errors.append("ui_language musí být 'cs' nebo 'en'")
        
        return errors


class ApplicationConfiguration:
    """
    Centralizovaná správa konfigurace s validací a persistence
    
    @description Implementuje type-safe konfiguraci s automatickým ukládáním
    """
    
    CONFIG_VERSION = "1.0"
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        auto_save: bool = True,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializace konfigurace s automatickým načtením
        
        @param config_path: Cesta ke konfiguračnímu souboru
        @param auto_save: Automaticky ukládat změny
        @param logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config_path = config_path or self._get_default_config_path()
        self.auto_save = auto_save
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Načtení nebo vytvoření konfigurace
        self.config = self._load_or_create_config()
        
        # Observer pattern
        self._observers: List[Callable[[str, Any, Any], None]] = []
        self._change_history: List[Dict[str, Any]] = []
        
        # Inicializace cest
        self._ensure_directories()
        
        self.logger.info(f"Konfigurace načtena z {self.config_path}")
    
    def _get_default_config_path(self) -> Path:
        """
        Určuje výchozí cestu ke konfiguraci podle platformy
        
        @returns: Cesta ke konfiguračnímu souboru
        """
        import platform
        
        if platform.system() == 'Darwin':  # macOS
            config_dir = Path.home() / 'Library' / 'Application Support' / 'MacActivityAnalyzer'
        elif platform.system() == 'Windows':
            config_dir = Path.home() / 'AppData' / 'Local' / 'MacActivityAnalyzer'
        else:  # Linux a ostatní
            config_dir = Path.home() / '.config' / 'mac-activity-analyzer'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'config.json'
    
    def _load_or_create_config(self) -> ConfigSchema:
        """
        Načítá existující konfiguraci nebo vytváří novou
        
        @returns: Načtená nebo výchozí konfigurace
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Kontrola verze
                version = data.get('_version', '0.0')
                if version != self.CONFIG_VERSION:
                    self.logger.warning(f"Konfigurace má jinou verzi ({version}), migruji na {self.CONFIG_VERSION}")
                    data = self._migrate_config(data, version)
                
                # Odstranění metadat
                data.pop('_version', None)
                data.pop('_updated_at', None)
                
                # Vytvoření ConfigSchema s načtenými daty
                config = ConfigSchema()
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                # Validace
                errors = config.validate()
                if errors:
                    self.logger.warning(f"Konfigurace obsahuje chyby: {errors}")
                    # Použití výchozích hodnot pro nevalidní položky
                    config = ConfigSchema()
                
                return config
                
            except Exception as e:
                self.logger.error(f"Chyba při načítání konfigurace: {e}")
                return ConfigSchema()
        else:
            # Vytvoření nové konfigurace
            config = ConfigSchema()
            self._save_config(config)
            return config
    
    def _save_config(self, config: ConfigSchema) -> bool:
        """
        Ukládá konfiguraci do souboru
        
        @param config: Konfigurace k uložení
        @returns: True pokud bylo uložení úspěšné
        """
        try:
            # Příprava dat k uložení
            data = asdict(config)
            data['_version'] = self.CONFIG_VERSION
            data['_updated_at'] = datetime.now().isoformat()
            
            # Atomické uložení přes temporary soubor
            temp_path = self.config_path.with_suffix('.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomický rename
            temp_path.replace(self.config_path)
            
            self.logger.debug("Konfigurace uložena")
            return True
            
        except Exception as e:
            self.logger.error(f"Chyba při ukládání konfigurace: {e}")
            return False
    
    def _migrate_config(self, data: Dict[str, Any], old_version: str) -> Dict[str, Any]:
        """
        Migruje konfiguraci ze starší verze
        
        @param data: Data konfigurace
        @param old_version: Stará verze
        @returns: Migrovaná data
        """
        self.logger.info(f"Migrace konfigurace z verze {old_version} na {self.CONFIG_VERSION}")
        
        # Zde by byly implementovány migrace mezi verzemi
        # Např. přejmenování klíčů, konverze formátů, atd.
        
        return data
    
    def _ensure_directories(self) -> None:
        """Zajišťuje existenci adresářů definovaných v konfiguraci"""
        with self._lock:
            # Nastavení výchozích cest pokud nejsou definovány
            base_dir = self.config_path.parent
            
            if not self.config.paths_data_dir:
                self.config.paths_data_dir = str(base_dir / 'data')
            
            if not self.config.paths_log_dir:
                self.config.paths_log_dir = str(base_dir / 'logs')
            
            if not self.config.paths_export_dir:
                self.config.paths_export_dir = str(base_dir / 'exports')
            
            # Vytvoření adresářů
            for path_attr in ['paths_data_dir', 'paths_log_dir', 'paths_export_dir']:
                path = Path(getattr(self.config, path_attr))
                path.mkdir(parents=True, exist_ok=True)
            
            # Uložení aktualizované konfigurace
            if self.auto_save:
                self._save_config(self.config)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Získává hodnotu z konfigurace pomocí tečkové notace
        
        @param key_path: Cesta ke klíči (např. 'analysis.retention_days')
        @param default: Výchozí hodnota pokud klíč neexistuje
        @returns: Hodnota konfigurace
        """
        with self._lock:
            # Převod tečkové notace na atribut
            key = key_path.replace('.', '_')
            
            if hasattr(self.config, key):
                return getattr(self.config, key)
            
            return default
    
    def set(self, key_path: str, value: Any) -> bool:
        """
        Nastavuje hodnotu v konfiguraci s automatickým uložením
        
        @param key_path: Cesta ke klíči
        @param value: Nová hodnota
        @returns: True pokud byla hodnota úspěšně nastavena
        """
        with self._lock:
            # Převod tečkové notace na atribut
            key = key_path.replace('.', '_')
            
            if not hasattr(self.config, key):
                self.logger.error(f"Neznámý konfigurační klíč: {key_path}")
                return False
            
            # Získání staré hodnoty
            old_value = getattr(self.config, key)
            
            # Nastavení nové hodnoty
            setattr(self.config, key, value)
            
            # Validace
            errors = self.config.validate()
            if errors:
                # Rollback při chybě validace
                setattr(self.config, key, old_value)
                self.logger.error(f"Validační chyba pro {key_path}: {errors}")
                return False
            
            # Uložení do historie
            self._change_history.append({
                'timestamp': datetime.now(),
                'key': key_path,
                'old_value': old_value,
                'new_value': value
            })
            
            # Automatické uložení
            if self.auto_save:
                self._save_config(self.config)
            
            # Notifikace observerů
            self._notify_observers(key_path, old_value, value)
            
            self.logger.debug(f"Konfigurace změněna: {key_path} = {value}")
            
            return True
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """
        Hromadná aktualizace více hodnot
        
        @param updates: Slovník s aktualizacemi
        @returns: True pokud byly všechny hodnoty úspěšně nastaveny
        """
        with self._lock:
            # Záloha současné konfigurace
            backup = copy.deepcopy(self.config)
            
            # Pokus o aplikaci všech změn
            all_success = True
            for key_path, value in updates.items():
                if not self.set(key_path, value):
                    all_success = False
                    break
            
            # Rollback při neúspěchu
            if not all_success:
                self.config = backup
                if self.auto_save:
                    self._save_config(self.config)
                
                self.logger.error("Hromadná aktualizace selhala, proveden rollback")
            
            return all_success
    
    def reset_to_defaults(self, key_path: Optional[str] = None) -> None:
        """
        Resetuje konfiguraci na výchozí hodnoty
        
        @param key_path: Konkrétní klíč k resetování (None = celá konfigurace)
        """
        with self._lock:
            if key_path:
                # Reset konkrétního klíče
                default_config = ConfigSchema()
                key = key_path.replace('.', '_')
                
                if hasattr(default_config, key):
                    default_value = getattr(default_config, key)
                    self.set(key_path, default_value)
                    self.logger.info(f"Klíč {key_path} resetován na výchozí hodnotu")
            else:
                # Reset celé konfigurace
                old_config = self.config
                self.config = ConfigSchema()
                
                if self.auto_save:
                    self._save_config(self.config)
                
                # Notifikace o všech změnách
                for attr in vars(old_config):
                    if not attr.startswith('_'):
                        old_value = getattr(old_config, attr)
                        new_value = getattr(self.config, attr)
                        if old_value != new_value:
                            key_path = attr.replace('_', '.')
                            self._notify_observers(key_path, old_value, new_value)
                
                self.logger.info("Konfigurace resetována na výchozí hodnoty")
    
    def export_config(self, path: Path) -> bool:
        """
        Exportuje konfiguraci do souboru
        
        @param path: Cesta pro export
        @returns: True pokud byl export úspěšný
        """
        with self._lock:
            try:
                data = asdict(self.config)
                data['_exported_at'] = datetime.now().isoformat()
                data['_version'] = self.CONFIG_VERSION
                
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Konfigurace exportována do {path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Chyba při exportu konfigurace: {e}")
                return False
    
    def import_config(self, path: Path) -> bool:
        """
        Importuje konfiguraci ze souboru
        
        @param path: Cesta k importovanému souboru
        @returns: True pokud byl import úspěšný
        """
        with self._lock:
            try:
                # Záloha současné konfigurace
                backup = copy.deepcopy(self.config)
                
                # Načtení nové konfigurace
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Odstranění metadat
                data.pop('_exported_at', None)
                data.pop('_version', None)
                
                # Aplikace importovaných hodnot
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                
                # Validace
                errors = self.config.validate()
                if errors:
                    # Rollback při chybě
                    self.config = backup
                    self.logger.error(f"Import selhal kvůli validačním chybám: {errors}")
                    return False
                
                # Uložení
                if self.auto_save:
                    self._save_config(self.config)
                
                self.logger.info(f"Konfigurace importována z {path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Chyba při importu konfigurace: {e}")
                return False
    
    def register_observer(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        Registruje observer pro změny konfigurace
        
        @param callback: Funkce volaná při změně (key_path, old_value, new_value)
        """
        with self._lock:
            self._observers.append(callback)
            self.logger.debug(f"Registrován observer: {callback}")
    
    def unregister_observer(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        Odregistruje observer
        
        @param callback: Funkce k odregistrování
        """
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)
                self.logger.debug(f"Odregistrován observer: {callback}")
    
    def _notify_observers(self, key_path: str, old_value: Any, new_value: Any) -> None:
        """
        Notifikuje observery o změně konfigurace
        
        @param key_path: Cesta ke změněnému klíči
        @param old_value: Stará hodnota
        @param new_value: Nová hodnota
        """
        for observer in self._observers:
            try:
                observer(key_path, old_value, new_value)
            except Exception as e:
                self.logger.error(f"Chyba v observeru konfigurace: {e}")
    
    def get_change_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Získává historii změn konfigurace
        
        @param limit: Maximální počet záznamů
        @returns: Seznam změn
        """
        with self._lock:
            if limit:
                return self._change_history[-limit:]
            return self._change_history.copy()
    
    def clear_change_history(self) -> None:
        """Vymazává historii změn"""
        with self._lock:
            self._change_history.clear()
            self.logger.debug("Historie změn konfigurace vymazána")
    
    def as_dict(self) -> Dict[str, Any]:
        """
        Vrací konfiguraci jako slovník
        
        @returns: Slovník s konfigurací
        """
        with self._lock:
            return asdict(self.config)
    
    def __str__(self) -> str:
        """String reprezentace konfigurace"""
        return json.dumps(self.as_dict(), indent=2, ensure_ascii=False)


# Ukázka použití
if __name__ == "__main__":
    # Nastavení loggeru
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Vytvoření konfigurace
    config = ApplicationConfiguration()
    
    # Observer pro změny
    def on_config_change(key_path: str, old_value: Any, new_value: Any):
        print(f"Konfigurace změněna: {key_path}: {old_value} -> {new_value}")
    
    config.register_observer(on_config_change)
    
    # Čtení hodnot
    print(f"Retention days: {config.get('analysis.retention_days')}")
    print(f"Hourly rate: {config.get('analysis.hourly_rate')}")
    
    # Změna hodnot
    config.set('analysis.hourly_rate', 300.0)
    config.set('ui.default_theme', 'dark')
    
    # Hromadná aktualizace
    config.update({
        'performance.thread_pool_size': 8,
        'ui.refresh_interval': 2000
    })
    
    # Export konfigurace
    export_path = Path("config_export.json")
    config.export_config(export_path)
    
    # Historie změn
    print("\nHistorie změn:")
    for change in config.get_change_history():
        print(f"  {change['timestamp']}: {change['key']} = {change['new_value']}")
    
    # Výpis celé konfigurace
    print(f"\nCelá konfigurace:\n{config}")