#!/usr/bin/env python3
"""
Logging Configuration Module

Poskytuje centralizovanou konfiguraci pro strukturované logování
s podporou rotace souborů, různých úrovní a kontextových informací.
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Union
import traceback


class ContextFilter(logging.Filter):
    """
    Filtr přidávající kontextové informace do log záznamů
    
    @description Obohacuje log záznamy o dodatečné kontextové informace
    """
    
    def __init__(self, app_name: str = "MacActivityAnalyzer", version: str = "1.0"):
        super().__init__()
        self.app_name = app_name
        self.version = version
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Přidává kontextové informace do záznamu"""
        record.app_name = self.app_name
        record.version = self.version
        record.hostname = self._get_hostname()
        record.user = self._get_username()
        
        # Přidání informací o vlákně
        if record.thread:
            record.thread_name = record.threadName
        
        return True
    
    @staticmethod
    def _get_hostname() -> str:
        """Získává hostname počítače"""
        import socket
        try:
            return socket.gethostname()
        except:
            return "unknown"
    
    @staticmethod
    def _get_username() -> str:
        """Získává jméno uživatele"""
        import os
        try:
            return os.getenv('USER', os.getenv('USERNAME', 'unknown'))
        except:
            return "unknown"


class StructuredFormatter(logging.Formatter):
    """
    Formátovač pro strukturované logování
    
    @description Vytváří strukturované log záznamy ve formátu JSON
    """
    
    def __init__(self, include_stacktrace: bool = True):
        super().__init__()
        self.include_stacktrace = include_stacktrace
    
    def format(self, record: logging.LogRecord) -> str:
        """Formátuje log záznam jako JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process_id': record.process,
            'thread_id': record.thread,
            'thread_name': getattr(record, 'thread_name', None)
        }
        
        # Přidání kontextových informací pokud existují
        if hasattr(record, 'app_name'):
            log_data['app_name'] = record.app_name
        if hasattr(record, 'version'):
            log_data['version'] = record.version
        if hasattr(record, 'hostname'):
            log_data['hostname'] = record.hostname
        if hasattr(record, 'user'):
            log_data['user'] = record.user
        
        # Přidání extra dat
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # Přidání exception info pokud existuje
        if record.exc_info and self.include_stacktrace:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'stacktrace': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Formátovač pro lidsky čitelné logy
    
    @description Vytváří čitelné log záznamy pro konzoli
    """
    
    # Barvy pro různé úrovně (ANSI escape codes)
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m'   # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors: bool = True, include_thread: bool = False):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
        self.include_thread = include_thread
    
    def format(self, record: logging.LogRecord) -> str:
        """Formátuje log záznam pro čitelný výstup"""
        # Základní formát
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        level = record.levelname
        logger = record.name
        
        # Zkrácení názvu loggeru
        if len(logger) > 30:
            parts = logger.split('.')
            if len(parts) > 2:
                logger = f"{parts[0]}...{parts[-1]}"
        
        # Přidání barvy pokud je povolena
        if self.use_colors and level in self.COLORS:
            level_str = f"{self.COLORS[level]}{level:8s}{self.RESET}"
        else:
            level_str = f"{level:8s}"
        
        # Základní zpráva
        message_parts = [
            timestamp,
            level_str,
            f"[{logger:30s}]",
            record.getMessage()
        ]
        
        # Přidání thread info pokud je požadováno
        if self.include_thread and record.thread:
            message_parts.insert(3, f"[{record.threadName}]")
        
        message = " ".join(message_parts)
        
        # Přidání exception info
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            message += f"\n{exception_text}"
        
        return message


class LoggingManager:
    """
    Centrální správce logování
    
    @description Poskytuje jednotné rozhraní pro konfiguraci logování
    """
    
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    def __init__(
        self,
        app_name: str = "MacActivityAnalyzer",
        version: str = "1.0",
        log_dir: Optional[Path] = None
    ):
        """
        Inicializace správce logování
        
        @param app_name: Název aplikace
        @param version: Verze aplikace
        @param log_dir: Adresář pro log soubory
        """
        self.app_name = app_name
        self.version = version
        self.log_dir = log_dir or self._get_default_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Context filter pro všechny handlery
        self.context_filter = ContextFilter(app_name, version)
        
        # Nastavené loggery
        self._configured_loggers: Dict[str, logging.Logger] = {}
    
    def _get_default_log_dir(self) -> Path:
        """Získává výchozí adresář pro logy"""
        import platform
        
        if platform.system() == 'Darwin':  # macOS
            log_dir = Path.home() / 'Library' / 'Logs' / self.app_name
        elif platform.system() == 'Windows':
            log_dir = Path.home() / 'AppData' / 'Local' / self.app_name / 'Logs'
        else:  # Linux a ostatní
            log_dir = Path.home() / '.local' / 'share' / self.app_name.lower() / 'logs'
        
        return log_dir
    
    def setup_root_logger(
        self,
        level: Union[str, int] = logging.INFO,
        console_output: bool = True,
        file_output: bool = True,
        structured_logs: bool = False
    ) -> logging.Logger:
        """
        Nastavuje root logger
        
        @param level: Úroveň logování
        @param console_output: Povolit výstup na konzoli
        @param file_output: Povolit výstup do souboru
        @param structured_logs: Použít strukturované logování (JSON)
        @returns: Nakonfigurovaný root logger
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Odstranění existujících handlerů
        root_logger.handlers = []
        
        # Přidání context filteru
        root_logger.addFilter(self.context_filter)
        
        # Console handler
        if console_output:
            console_handler = self._create_console_handler(structured_logs)
            root_logger.addHandler(console_handler)
        
        # File handler
        if file_output:
            file_handler = self._create_file_handler(
                'app.log',
                structured_logs,
                max_bytes=10 * 1024 * 1024,  # 10 MB
                backup_count=5
            )
            root_logger.addHandler(file_handler)
        
        return root_logger
    
    def setup_logger(
        self,
        name: str,
        level: Union[str, int] = logging.INFO,
        console_output: bool = True,
        file_output: bool = True,
        file_name: Optional[str] = None,
        structured_logs: bool = False
    ) -> logging.Logger:
        """
        Nastavuje specifický logger
        
        @param name: Název loggeru
        @param level: Úroveň logování
        @param console_output: Povolit výstup na konzoli
        @param file_output: Povolit výstup do souboru
        @param file_name: Název log souboru (výchozí: {name}.log)
        @param structured_logs: Použít strukturované logování
        @returns: Nakonfigurovaný logger
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        
        # Odstranění existujících handlerů
        logger.handlers = []
        
        # Přidání context filteru
        logger.addFilter(self.context_filter)
        
        # Console handler
        if console_output:
            console_handler = self._create_console_handler(structured_logs)
            logger.addHandler(console_handler)
        
        # File handler
        if file_output:
            if file_name is None:
                file_name = f"{name.replace('.', '_')}.log"
            
            file_handler = self._create_file_handler(
                file_name,
                structured_logs,
                max_bytes=5 * 1024 * 1024,  # 5 MB
                backup_count=3
            )
            logger.addHandler(file_handler)
        
        # Uložení reference
        self._configured_loggers[name] = logger
        
        return logger
    
    def _create_console_handler(
        self,
        structured: bool = False
    ) -> logging.StreamHandler:
        """Vytváří console handler"""
        handler = logging.StreamHandler(sys.stdout)
        
        if structured:
            formatter = StructuredFormatter(include_stacktrace=False)
        else:
            formatter = HumanReadableFormatter(use_colors=True, include_thread=True)
        
        handler.setFormatter(formatter)
        handler.addFilter(self.context_filter)
        
        return handler
    
    def _create_file_handler(
        self,
        filename: str,
        structured: bool = False,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5
    ) -> logging.handlers.RotatingFileHandler:
        """Vytváří rotating file handler"""
        log_path = self.log_dir / filename
        
        handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        if structured:
            formatter = StructuredFormatter(include_stacktrace=True)
        else:
            formatter = logging.Formatter(self.DEFAULT_FORMAT)
        
        handler.setFormatter(formatter)
        handler.addFilter(self.context_filter)
        
        return handler
    
    def setup_error_logger(
        self,
        file_name: str = 'errors.log',
        email_errors: bool = False,
        email_config: Optional[Dict[str, Any]] = None
    ) -> logging.Logger:
        """
        Nastavuje speciální logger pro chyby
        
        @param file_name: Název souboru pro chyby
        @param email_errors: Posílat chyby emailem
        @param email_config: Konfigurace pro email handler
        @returns: Error logger
        """
        error_logger = self.setup_logger(
            'errors',
            level=logging.ERROR,
            console_output=True,
            file_output=True,
            file_name=file_name,
            structured_logs=True
        )
        
        # Email handler pokud je požadován
        if email_errors and email_config:
            email_handler = self._create_email_handler(email_config)
            if email_handler:
                error_logger.addHandler(email_handler)
        
        return error_logger
    
    def _create_email_handler(
        self,
        config: Dict[str, Any]
    ) -> Optional[logging.handlers.SMTPHandler]:
        """Vytváří SMTP handler pro posílání chyb emailem"""
        try:
            mailhost = config.get('mailhost', 'localhost')
            fromaddr = config.get('fromaddr')
            toaddrs = config.get('toaddrs', [])
            subject = config.get('subject', f'{self.app_name} Error')
            credentials = config.get('credentials')
            secure = config.get('secure')
            
            if not fromaddr or not toaddrs:
                return None
            
            handler = logging.handlers.SMTPHandler(
                mailhost=mailhost,
                fromaddr=fromaddr,
                toaddrs=toaddrs,
                subject=subject,
                credentials=credentials,
                secure=secure
            )
            
            handler.setLevel(logging.ERROR)
            handler.setFormatter(logging.Formatter(self.DEFAULT_FORMAT))
            
            return handler
            
        except Exception as e:
            print(f"Nepodařilo se vytvořit email handler: {e}")
            return None
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Získává logger podle jména
        
        @param name: Název loggeru
        @returns: Logger instance
        """
        if name in self._configured_loggers:
            return self._configured_loggers[name]
        return logging.getLogger(name)
    
    def set_level(self, logger_name: str, level: Union[str, int]) -> None:
        """
        Nastavuje úroveň pro konkrétní logger
        
        @param logger_name: Název loggeru
        @param level: Nová úroveň
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    def add_context(self, **context) -> None:
        """
        Přidává globální kontext pro všechny logy
        
        @param context: Kontextová data
        """
        for key, value in context.items():
            setattr(self.context_filter, key, value)
    
    def log_with_context(
        self,
        logger_name: str,
        level: Union[str, int],
        message: str,
        **extra_data
    ) -> None:
        """
        Loguje zprávu s dodatečným kontextem
        
        @param logger_name: Název loggeru
        @param level: Úroveň logu
        @param message: Zpráva
        @param extra_data: Dodatečná data
        """
        logger = self.get_logger(logger_name)
        
        # Vytvoření log záznamu s extra daty
        log_record = logger.makeRecord(
            logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            None
        )
        log_record.extra_data = extra_data
        
        logger.handle(log_record)
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """
        Maže staré log soubory
        
        @param days: Počet dní k uchování
        @returns: Počet smazaných souborů
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for log_file in self.log_dir.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    log_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Nepodařilo se smazat {log_file}: {e}")
        
        return deleted_count


# Singleton instance
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """
    Získává singleton instanci LoggingManager
    
    @returns: LoggingManager instance
    """
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager


def setup_logging(
    app_name: str = "MacActivityAnalyzer",
    version: str = "1.0",
    log_level: Union[str, int] = logging.INFO,
    structured: bool = False,
    log_dir: Optional[Path] = None
) -> None:
    """
    Rychlé nastavení logování pro aplikaci
    
    @param app_name: Název aplikace
    @param version: Verze aplikace
    @param log_level: Úroveň logování
    @param structured: Použít strukturované logování
    @param log_dir: Adresář pro log soubory
    """
    manager = LoggingManager(app_name, version, log_dir)
    
    # Nastavení root loggeru
    manager.setup_root_logger(
        level=log_level,
        console_output=True,
        file_output=True,
        structured_logs=structured
    )
    
    # Nastavení error loggeru
    manager.setup_error_logger()
    
    # Uložení jako singleton
    global _logging_manager
    _logging_manager = manager


# Ukázka použití
if __name__ == "__main__":
    # Rychlé nastavení
    setup_logging(
        app_name="TestApp",
        version="1.0",
        log_level=logging.DEBUG,
        structured=False
    )
    
    # Získání loggeru
    logger = logging.getLogger(__name__)
    
    # Různé úrovně logování
    logger.debug("Debug zpráva")
    logger.info("Informační zpráva")
    logger.warning("Varování")
    logger.error("Chyba")
    
    # Logování s exception
    try:
        1 / 0
    except Exception:
        logger.exception("Zachycena výjimka")
    
    # Strukturované logování s kontextem
    manager = get_logging_manager()
    manager.log_with_context(
        __name__,
        logging.INFO,
        "Operace dokončena",
        operation="test",
        duration=1.5,
        result="success"
    )
    
    # Vyčištění starých logů
    deleted = manager.cleanup_old_logs(days=7)
    logger.info(f"Smazáno {deleted} starých log souborů")