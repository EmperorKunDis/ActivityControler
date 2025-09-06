#!/usr/bin/env python3
"""
Mac Activity Analyzer - Advanced Secure Version
Bezpečná verze s ochranou proti shell injection a robustním zpracováním
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
from collections import defaultdict, Counter
import threading
import queue
import json
import logging
import logging.handlers
import subprocess
import shlex
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import io
from contextlib import contextmanager
import time

# ================== Bezpečnostní komponenty ==================

class SecurityError(Exception):
    """Výjimka pro bezpečnostní problémy"""
    pass

class ValidationError(Exception):
    """Výjimka pro validační chyby"""
    pass

@dataclass
class CommandResult:
    """Výsledek bezpečného spuštění příkazu"""
    stdout: str
    stderr: str
    return_code: int
    execution_time: float

class SecureCommandExecutor:
    """Bezpečné spouštění shell příkazů s ochranou proti injection"""
    
    ALLOWED_COMMANDS = {
        'pmset': ['/usr/bin/pmset'],
        'last': ['/usr/bin/last'],
        'who': ['/usr/bin/who'],
        'uptime': ['/usr/bin/uptime']
    }
    
    MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10MB limit
    DEFAULT_TIMEOUT = 30  # seconds
    
    @classmethod
    def execute(cls, command: str, args: List[str], timeout: Optional[float] = None) -> CommandResult:
        """Bezpečné spuštění příkazu s validací"""
        start_time = time.time()
        
        if command not in cls.ALLOWED_COMMANDS:
            raise SecurityError(f"Příkaz '{command}' není povolen")
            
        cmd_path = cls.ALLOWED_COMMANDS[command][0]
        if not os.path.exists(cmd_path):
            raise SecurityError(f"Příkaz '{cmd_path}' neexistuje")
            
        # Validace argumentů
        safe_args = []
        for arg in args:
            if not cls._validate_argument(arg):
                raise SecurityError(f"Neplatný argument: {arg}")
            safe_args.append(arg)
            
        full_command = [cmd_path] + safe_args
        
        try:
            # Spustit příkaz bez shell=True
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=cls._get_safe_environment()
            )
            
            stdout, stderr = process.communicate(timeout=timeout or cls.DEFAULT_TIMEOUT)
            
            # Kontrola velikosti výstupu
            if len(stdout) > cls.MAX_OUTPUT_SIZE:
                stdout = stdout[:cls.MAX_OUTPUT_SIZE] + "\n[ZKRÁCENO - PŘEKROČEN LIMIT]"
                
            return CommandResult(
                stdout=stdout,
                stderr=stderr,
                return_code=process.returncode,
                execution_time=time.time() - start_time
            )
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise SecurityError(f"Příkaz překročil časový limit {timeout}s")
        except Exception as e:
            raise SecurityError(f"Chyba při spouštění příkazu: {str(e)}")
            
    @staticmethod
    def _validate_argument(arg: str) -> bool:
        """Validace argumentu proti nebezpečným znakům"""
        # Povolit pouze bezpečné znaky
        if re.match(r'^[a-zA-Z0-9\s\-_./:\[\]]+$', arg):
            return True
        return False
        
    @staticmethod
    def _get_safe_environment() -> Dict[str, str]:
        """Získat bezpečné prostředí pro spuštění příkazu"""
        safe_env = {
            'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
            'LC_ALL': 'C',
            'LANG': 'C'
        }
        return safe_env

# ================== Robustní parsing logů ==================

@dataclass
class LogEvent:
    """Strukturovaná událost z logu"""
    timestamp: datetime
    event_type: str
    category: str
    description: str
    details: Optional[str] = None
    app: Optional[str] = None
    pid: Optional[str] = None
    action: Optional[str] = None

class LogParser:
    """Základní třída pro parsování logů"""
    
    def parse(self, log_data: str) -> List[LogEvent]:
        """Parse log data into events"""
        raise NotImplementedError
        
    def validate_timestamp(self, timestamp_str: str, format: str) -> Optional[datetime]:
        """Bezpečně parsovat timestamp"""
        try:
            return datetime.strptime(timestamp_str, format)
        except ValueError:
            return None

class DisplayLogParser(LogParser):
    """Parser pro display eventy"""
    
    DISPLAY_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^\n]*Display\s+is\s+turned\s+(on|off)',
        re.IGNORECASE
    )
    
    def parse(self, log_data: str) -> List[LogEvent]:
        events = []
        
        for match in self.DISPLAY_PATTERN.finditer(log_data):
            timestamp = self.validate_timestamp(match.group(1), '%Y-%m-%d %H:%M:%S')
            if not timestamp:
                continue
                
            state = match.group(2).lower()
            events.append(LogEvent(
                timestamp=timestamp,
                event_type=f'display_{state}',
                category='display',
                description=f'Display {"zapnut" if state == "on" else "vypnut"}'
            ))
            
        return events

class SleepWakeLogParser(LogParser):
    """Parser pro sleep/wake eventy"""
    
    SLEEP_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^\n]*(Entering\s+Sleep|Sleep\s+Entering)[^\n]*',
        re.IGNORECASE
    )
    
    WAKE_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^\n]*(DarkWake|Wake\s+from)[^\n]*',
        re.IGNORECASE
    )
    
    def parse(self, log_data: str) -> List[LogEvent]:
        events = []
        
        # Parse sleep events
        for match in self.SLEEP_PATTERN.finditer(log_data):
            timestamp = self.validate_timestamp(match.group(1), '%Y-%m-%d %H:%M:%S')
            if not timestamp:
                continue
                
            line = match.group(0)
            reason = self._determine_sleep_reason(line)
            
            events.append(LogEvent(
                timestamp=timestamp,
                event_type='sleep',
                category='power',
                description=f'Uspání: {reason}',
                details=line
            ))
            
        # Parse wake events
        for match in self.WAKE_PATTERN.finditer(log_data):
            timestamp = self.validate_timestamp(match.group(1), '%Y-%m-%d %H:%M:%S')
            if not timestamp:
                continue
                
            line = match.group(0)
            wake_type, desc = self._determine_wake_type(line)
            
            events.append(LogEvent(
                timestamp=timestamp,
                event_type=wake_type,
                category='power',
                description=desc,
                details=line
            ))
            
        return events
        
    def _determine_sleep_reason(self, line: str) -> str:
        """Určit důvod uspání"""
        if "Clamshell Sleep" in line:
            return "Zavření víka"
        elif "Maintenance Sleep" in line:
            return "Automatické uspání"
        elif "Software Sleep" in line:
            return "Manuální uspání"
        return "Neznámý důvod"
        
    def _determine_wake_type(self, line: str) -> Tuple[str, str]:
        """Určit typ probuzení"""
        if "DarkWake to FullWake" in line:
            return 'wake_full', 'Plné probuzení'
        elif "DarkWake" in line:
            return 'wake_dark', 'Probuzení na pozadí'
        return 'wake', 'Probuzení'

class BootShutdownLogParser(LogParser):
    """Parser pro boot/shutdown eventy"""
    
    REBOOT_PATTERN = re.compile(
        r'reboot\s+~[^\n]+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})',
        re.IGNORECASE
    )
    
    SHUTDOWN_PATTERN = re.compile(
        r'shutdown\s+~[^\n]+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})',
        re.IGNORECASE
    )
    
    def parse(self, log_data: str) -> List[LogEvent]:
        events = []
        current_year = datetime.now().year
        
        # Parse reboots
        for match in self.REBOOT_PATTERN.finditer(log_data):
            timestamp = self._parse_last_timestamp(match.group(1), current_year)
            if timestamp:
                events.append(LogEvent(
                    timestamp=timestamp,
                    event_type='boot',
                    category='system',
                    description='Start systému'
                ))
                
        # Parse shutdowns
        for match in self.SHUTDOWN_PATTERN.finditer(log_data):
            timestamp = self._parse_last_timestamp(match.group(1), current_year)
            if timestamp:
                events.append(LogEvent(
                    timestamp=timestamp,
                    event_type='shutdown',
                    category='system',
                    description='Vypnutí systému'
                ))
                
        return events
        
    def _parse_last_timestamp(self, date_str: str, year: int) -> Optional[datetime]:
        """Parse timestamp from 'last' command output"""
        try:
            timestamp = datetime.strptime(f"{date_str} {year}", '%a %b %d %H:%M %Y')
            if timestamp > datetime.now():
                timestamp = timestamp.replace(year=year - 1)
            return timestamp
        except ValueError:
            return None

class AssertionLogParser(LogParser):
    """Parser pro power assertions (aktivita aplikací)"""
    
    ASSERTION_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^\n]*'
        r'PID\s+(\d+)\(([^)]+)\)\s+(\w+)\s+([^\n]+)',
        re.IGNORECASE
    )
    
    def parse(self, log_data: str) -> List[LogEvent]:
        events = []
        
        for match in self.ASSERTION_PATTERN.finditer(log_data):
            timestamp = self.validate_timestamp(match.group(1), '%Y-%m-%d %H:%M:%S')
            if not timestamp:
                continue
                
            events.append(LogEvent(
                timestamp=timestamp,
                event_type='assertion',
                category='app',
                pid=match.group(2),
                app=match.group(3),
                action=match.group(4),
                description=f'{match.group(3)}: {match.group(4)}',
                details=match.group(5)
            ))
            
        return events

class CompositeLogParser:
    """Kombinovaný parser pro všechny typy logů"""
    
    def __init__(self):
        self.parsers = {
            'display': DisplayLogParser(),
            'sleep_wake': SleepWakeLogParser(),
            'boot_shutdown': BootShutdownLogParser(),
            'assertions': AssertionLogParser()
        }
        
    def parse_all(self, log_data: Dict[str, str]) -> List[LogEvent]:
        """Parse všechny typy logů"""
        all_events = []
        
        for log_type, parser in self.parsers.items():
            if log_type in log_data and log_data[log_type]:
                try:
                    events = parser.parse(log_data[log_type])
                    all_events.extend(events)
                except Exception as e:
                    logging.error(f"Chyba při parsování {log_type}: {str(e)}")
                    
        # Seřadit podle timestamp
        all_events.sort(key=lambda x: x.timestamp)
        return all_events

# ================== Správa konfigurace ==================

@dataclass
class ApplicationConfiguration:
    """Centrální konfigurace aplikace"""
    
    # GUI nastavení
    window_title: str = "Mac Activity Analyzer - Advanced Secure"
    window_geometry: str = "1400x900"
    
    # Analýza
    analysis_days: int = 10
    activity_threshold_seconds: int = 60
    
    # Finance
    default_hourly_rate: float = 250.0
    currency: str = "Kč"
    
    # Limity
    max_events: int = 10000
    max_log_lines: int = 1000
    memory_limit_mb: int = 500
    
    # Bezpečnost
    command_timeout: int = 30
    max_file_size_mb: int = 100
    
    # Export
    export_formats: List[str] = field(default_factory=lambda: ['.txt', '.json', '.csv'])
    
    def validate(self) -> bool:
        """Validovat konfiguraci"""
        if self.analysis_days < 1 or self.analysis_days > 365:
            raise ValidationError("analysis_days musí být mezi 1 a 365")
        if self.activity_threshold_seconds < 1:
            raise ValidationError("activity_threshold_seconds musí být kladné")
        if self.memory_limit_mb < 50:
            raise ValidationError("memory_limit_mb musí být alespoň 50 MB")
        return True

# ================== Správa logování ==================

class LoggingManager:
    """Centrální správa logování"""
    
    @staticmethod
    def setup_logging(log_level=logging.INFO):
        """Nastavit strukturované logování"""
        
        # Vytvořit log adresář
        log_dir = Path.home() / '.mac_activity_analyzer' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Hlavní log soubor
        log_file = log_dir / f'activity_analyzer_{datetime.now():%Y%m%d}.log'
        
        # Formát logů
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler s rotací
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Nastavit root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Potlačit některé verbose knihovny
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        logging.getLogger('PIL').setLevel(logging.WARNING)

# ================== Zpracování dat s limity paměti ==================

class StreamingEventProcessor:
    """Streamové zpracování eventů s kontrolou paměti"""
    
    def __init__(self, memory_limit_mb: int = 500):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.processed_count = 0
        self.dropped_count = 0
        
    def process_events(self, events: List[LogEvent], max_events: int) -> List[LogEvent]:
        """Zpracovat eventy s limity"""
        
        # Kontrola počtu
        if len(events) > max_events:
            logging.warning(f"Příliš mnoho eventů ({len(events)}), omezuji na {max_events}")
            events = events[:max_events]
            self.dropped_count = len(events) - max_events
            
        # Kontrola paměti (zjednodušená)
        estimated_size = len(events) * 1000  # Přibližný odhad
        if estimated_size > self.memory_limit_bytes:
            keep_ratio = self.memory_limit_bytes / estimated_size
            keep_count = int(len(events) * keep_ratio)
            
            logging.warning(f"Omezuji eventy kvůli paměti na {keep_count}")
            events = events[:keep_count]
            self.dropped_count += len(events) - keep_count
            
        self.processed_count = len(events)
        return events

# ================== Thread-safe správa analýzy ==================

class ThreadSafeAnalysisManager:
    """Thread-safe správa analýz"""
    
    def __init__(self, message_queue: queue.Queue):
        self.message_queue = message_queue
        self.analysis_lock = threading.Lock()
        self.is_analyzing = False
        self.cancel_requested = False
        
    def start_analysis(self, target_func, *args):
        """Spustit analýzu v threadu"""
        with self.analysis_lock:
            if self.is_analyzing:
                logging.warning("Analýza již běží")
                return False
                
            self.is_analyzing = True
            self.cancel_requested = False
            
        thread = threading.Thread(
            target=self._run_analysis,
            args=(target_func, args),
            daemon=True
        )
        thread.start()
        return True
        
    def _run_analysis(self, target_func, args):
        """Wrapper pro bezpečné spuštění analýzy"""
        try:
            target_func(*args)
        except Exception as e:
            logging.error(f"Chyba v analýze: {str(e)}", exc_info=True)
            self.message_queue.put({
                'type': 'error',
                'text': f'Chyba při analýze: {str(e)}'
            })
        finally:
            with self.analysis_lock:
                self.is_analyzing = False
                
    def cancel_analysis(self):
        """Požádat o zrušení analýzy"""
        self.cancel_requested = True
        
    def should_continue(self) -> bool:
        """Zkontrolovat, zda má analýza pokračovat"""
        return not self.cancel_requested

# ================== Hlavní aplikace ==================

class MacActivityAdvancedSecure:
    def __init__(self, root):
        self.root = root
        self.config = ApplicationConfiguration()
        self.config.validate()
        
        self.root.title(self.config.window_title)
        self.root.geometry(self.config.window_geometry)
        
        # Nastavit logování
        LoggingManager.setup_logging()
        logging.info("Spouštím Mac Activity Analyzer - Secure Version")
        
        # Inicializace dat
        self.all_events = []
        self.states = []
        self.parsed_data = {
            'reboots': [],
            'shutdowns': [],
            'wake_events': [],
            'sleep_events': [],
            'display_events': [],
            'assertions': [],
            'app_activity': defaultdict(list)
        }
        
        # Komponenty
        self.message_queue = queue.Queue()
        self.analysis_manager = ThreadSafeAnalysisManager(self.message_queue)
        self.command_executor = SecureCommandExecutor()
        self.composite_parser = CompositeLogParser()
        self.event_processor = StreamingEventProcessor(self.config.memory_limit_mb)
        
        # GUI
        self.setup_ui()
        
        # Automaticky spustit analýzu
        self.root.after(100, self.start_analysis)
        
    def setup_ui(self):
        """Setup the main UI components"""
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Activity Graph
        self.graph_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text="📊 Graf aktivity")
        self.setup_graph_tab()
        
        # Tab 2: Overview
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="📋 Přehled")
        self.setup_overview_tab()
        
        # Tab 3: Application Analysis
        self.apps_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.apps_frame, text="📱 Aplikace")
        self.setup_apps_tab()
        
        # Tab 4: Sleep Analysis
        self.sleep_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sleep_frame, text="😴 Spánek/Probuzení")
        self.setup_sleep_tab()
        
        # Tab 5: Statistics
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="📈 Statistiky")
        self.setup_stats_tab()
        
        # Tab 6: Timeline
        self.timeline_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timeline_frame, text="🕒 Timeline")
        self.setup_timeline_tab()
        
        # Tab 7: Finance
        self.finance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.finance_frame, text="💰 Finance")
        self.setup_finance_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Připraven k analýze")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(fill='x', side='bottom', padx=5, pady=2)
        
        # Button bar
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Button(button_frame, text="🔄 Obnovit", command=self.start_analysis).pack(side='left', padx=2)
        ttk.Button(button_frame, text="💾 Export", command=self.export_data).pack(side='left', padx=2)
        ttk.Button(button_frame, text="📁 Načíst soubor", command=self.load_from_file).pack(side='left', padx=2)
        ttk.Button(button_frame, text="⚙️ Nastavení", command=self.show_settings).pack(side='left', padx=2)
        
        # Periodické zpracování fronty
        self.process_queue()
        
    def setup_graph_tab(self):
        """Setup activity graph tab"""
        # Matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(14, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Info frame
        self.info_frame = ttk.LabelFrame(self.graph_frame, text="Klikněte na graf pro detaily")
        self.info_frame.pack(fill='x', padx=5, pady=5)
        
        self.info_text = tk.Text(self.info_frame, height=5, wrap='word')
        self.info_text.pack(fill='x', padx=5, pady=5)
        
    def setup_overview_tab(self):
        """Setup the overview tab"""
        self.overview_text = scrolledtext.ScrolledText(self.overview_frame,
                                                       height=30, width=100,
                                                       wrap=tk.WORD)
        self.overview_text.pack(fill='both', expand=True, padx=10, pady=10)
        
    def setup_apps_tab(self):
        """Setup the applications analysis tab"""
        # Frame pro grafy
        graphs_frame = ttk.Frame(self.apps_frame)
        graphs_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Canvas pro graf aplikací
        self.app_fig, (self.app_pie_ax, self.app_timeline_ax) = plt.subplots(1, 2, figsize=(12, 5))
        self.app_canvas = FigureCanvasTkAgg(self.app_fig, master=graphs_frame)
        self.app_canvas.draw()
        self.app_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Text pro detaily
        self.apps_text = scrolledtext.ScrolledText(self.apps_frame,
                                                   height=10, width=100,
                                                   wrap=tk.WORD)
        self.apps_text.pack(fill='x', padx=10, pady=5)
        
    def setup_sleep_tab(self):
        """Setup the sleep/wake analysis tab"""
        # Frame pro grafy
        sleep_graphs = ttk.Frame(self.sleep_frame)
        sleep_graphs.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Canvas pro sleep grafy
        self.sleep_fig, self.sleep_ax = plt.subplots(figsize=(12, 6))
        self.sleep_canvas = FigureCanvasTkAgg(self.sleep_fig, master=sleep_graphs)
        self.sleep_canvas.draw()
        self.sleep_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Text
        self.sleep_text = scrolledtext.ScrolledText(self.sleep_frame,
                                                    height=10, width=100,
                                                    wrap=tk.WORD)
        self.sleep_text.pack(fill='x', padx=10, pady=5)
        
    def setup_stats_tab(self):
        """Setup the statistics tab"""
        # Frame pro histogram
        hist_frame = ttk.Frame(self.stats_frame)
        hist_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Canvas pro histogram
        self.stats_fig, (self.hour_ax, self.day_ax) = plt.subplots(2, 1, figsize=(12, 8))
        self.stats_canvas = FigureCanvasTkAgg(self.stats_fig, master=hist_frame)
        self.stats_canvas.draw()
        self.stats_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Text
        self.stats_text = scrolledtext.ScrolledText(self.stats_frame,
                                                    height=10, width=100,
                                                    wrap=tk.WORD)
        self.stats_text.pack(fill='x', padx=10, pady=5)
        
    def setup_timeline_tab(self):
        """Setup the timeline tab"""
        # Canvas for timeline visualization
        canvas_frame = ttk.Frame(self.timeline_frame)
        canvas_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.timeline_canvas = tk.Canvas(canvas_frame, height=400, bg='white')
        self.timeline_canvas.pack(fill='both', expand=True)
        
        # Timeline details
        self.timeline_text = scrolledtext.ScrolledText(self.timeline_frame,
                                                       height=15, width=100,
                                                       wrap=tk.WORD,
                                                       font=('Courier', 10))
        self.timeline_text.pack(fill='x', padx=10, pady=5)
        
    def setup_finance_tab(self):
        """Setup finance tab"""
        # Settings frame
        settings_frame = ttk.LabelFrame(self.finance_frame, text="Nastavení")
        settings_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(settings_frame, text="Hodinová sazba (Kč):").pack(side='left', padx=5)
        self.hourly_rate_var = tk.StringVar(value=str(self.config.default_hourly_rate))
        ttk.Entry(settings_frame, textvariable=self.hourly_rate_var, width=10).pack(side='left', padx=5)
        ttk.Button(settings_frame, text="Přepočítat", command=self.update_finance).pack(side='left', padx=5)
        
        # Finance text
        self.finance_text = scrolledtext.ScrolledText(self.finance_frame,
                                                      height=25, width=100,
                                                      wrap=tk.WORD)
        self.finance_text.pack(fill='both', expand=True, padx=10, pady=5)
        
    def process_queue(self):
        """Zpracovat zprávy z fronty"""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                
                if msg['type'] == 'status':
                    self.status_var.set(msg['text'])
                elif msg['type'] == 'complete':
                    self.update_all_displays()
                elif msg['type'] == 'error':
                    messagebox.showerror("Chyba", msg['text'])
                    
        except queue.Empty:
            pass
            
        self.root.after(100, self.process_queue)
        
    def start_analysis(self):
        """Spustit analýzu v threadu"""
        self.analysis_manager.start_analysis(self.analyze_activity)
        
    def analyze_activity(self):
        """Hlavní analýza aktivity - BEZPEČNÁ VERZE"""
        try:
            self.message_queue.put({'type': 'status', 'text': 'Načítám data z pmset logu...'})
            
            # Reset dat
            self.all_events = []
            self.parsed_data = {
                'reboots': [],
                'shutdowns': [],
                'wake_events': [],
                'sleep_events': [],
                'display_events': [],
                'assertions': [],
                'app_activity': defaultdict(list)
            }
            
            log_data = {}
            
            # 1. Display eventy - BEZPEČNÉ
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Analyzuji display eventy...'})
                result = self.command_executor.execute('pmset', ['-g', 'log'])
                if result.return_code == 0:
                    # Filtrovat pouze display eventy
                    display_logs = '\n'.join(line for line in result.stdout.split('\n') 
                                           if 'Display is turned' in line)[-self.config.max_log_lines:]
                    log_data['display'] = display_logs
            
            # 2. Sleep/Wake eventy - BEZPEČNÉ
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Analyzuji sleep/wake eventy...'})
                result = self.command_executor.execute('pmset', ['-g', 'log'])
                if result.return_code == 0:
                    # Filtrovat sleep/wake eventy
                    sleep_wake_logs = '\n'.join(line for line in result.stdout.split('\n') 
                                              if any(x in line for x in ['Entering Sleep', 'DarkWake', 'Wake from']))[-self.config.max_log_lines:]
                    log_data['sleep_wake'] = sleep_wake_logs
            
            # 3. Boot/Shutdown eventy - BEZPEČNÉ
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Analyzuji boot/shutdown eventy...'})
                
                # Reboot
                result = self.command_executor.execute('last', ['reboot'])
                if result.return_code == 0:
                    log_data['boot_shutdown'] = result.stdout[:self.config.max_log_lines]
                    
                # Shutdown
                result = self.command_executor.execute('last', ['shutdown'])
                if result.return_code == 0:
                    log_data['boot_shutdown'] += '\n' + result.stdout[:self.config.max_log_lines]
            
            # 4. Power assertions (aplikace) - BEZPEČNÉ
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Analyzuji aktivitu aplikací...'})
                result = self.command_executor.execute('pmset', ['-g', 'log'])
                if result.return_code == 0:
                    # Filtrovat assertion eventy
                    assertion_logs = '\n'.join(line for line in result.stdout.split('\n') 
                                             if 'Assertions' in line)[-self.config.max_log_lines:]
                    log_data['assertions'] = assertion_logs
            
            # Parsovat všechny logy
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Parsování eventů...'})
                all_events = self.composite_parser.parse_all(log_data)
                
                # Zpracovat s limity
                all_events = self.event_processor.process_events(all_events, self.config.max_events)
                
                # Omezit na posledních N dní
                cutoff_date = datetime.now() - timedelta(days=self.config.analysis_days)
                all_events = [e for e in all_events if e.timestamp > cutoff_date]
                
                # Převést na starý formát pro kompatibilitu
                self.all_events = self._convert_to_old_format(all_events)
                
                # Rozdělit podle typu
                self._categorize_events(all_events)
                
            # Vytvořit stavy
            if self.analysis_manager.should_continue():
                self.message_queue.put({'type': 'status', 'text': 'Vytvářím časové stavy...'})
                self.states = self.create_states_from_events(self.all_events)
            
            self.message_queue.put({'type': 'complete'})
            self.message_queue.put({'type': 'status', 'text': f'Analýza dokončena - {len(self.all_events)} eventů'})
            
        except SecurityError as e:
            logging.error(f"Bezpečnostní chyba: {str(e)}")
            self.message_queue.put({'type': 'error', 'text': f'Bezpečnostní chyba: {str(e)}'})
        except Exception as e:
            logging.error(f"Chyba při analýze: {str(e)}", exc_info=True)
            self.message_queue.put({'type': 'error', 'text': f'Chyba při analýze: {str(e)}'})
            
    def _convert_to_old_format(self, events: List[LogEvent]) -> List[Dict]:
        """Převést LogEvent objekty na starý formát slovníků"""
        old_format = []
        for event in events:
            old_event = {
                'timestamp': event.timestamp,
                'type': event.event_type,
                'category': event.category,
                'description': event.description
            }
            if event.details:
                old_event['details'] = event.details
            if event.app:
                old_event['app'] = event.app
            if event.pid:
                old_event['pid'] = event.pid
            if event.action:
                old_event['action'] = event.action
                
            old_format.append(old_event)
            
        return old_format
        
    def _categorize_events(self, events: List[LogEvent]):
        """Rozdělit eventy podle kategorií"""
        for event in events:
            if event.event_type == 'boot':
                self.parsed_data['reboots'].append(self._convert_event(event))
            elif event.event_type == 'shutdown':
                self.parsed_data['shutdowns'].append(self._convert_event(event))
            elif event.event_type in ['wake_full', 'wake_dark', 'wake']:
                self.parsed_data['wake_events'].append(self._convert_event(event))
            elif event.event_type == 'sleep':
                self.parsed_data['sleep_events'].append(self._convert_event(event))
            elif event.event_type in ['display_on', 'display_off']:
                self.parsed_data['display_events'].append(self._convert_event(event))
            elif event.event_type == 'assertion':
                assertion_dict = self._convert_event(event)
                self.parsed_data['assertions'].append(assertion_dict)
                if event.app:
                    self.parsed_data['app_activity'][event.app].append(assertion_dict)
                    
    def _convert_event(self, event: LogEvent) -> Dict:
        """Převést LogEvent na slovník pro zpětnou kompatibilitu"""
        return {
            'timestamp': event.timestamp,
            'type': event.event_type,
            'category': event.category,
            'description': event.description,
            'details': event.details,
            'app': getattr(event, 'app', None),
            'pid': getattr(event, 'pid', None),
            'action': getattr(event, 'action', None)
        }
        
    def create_states_from_events(self, events):
        """Vytvořit stavy z eventů"""
        states = []
        
        if not events:
            return states
            
        # Stav systému
        system_on = False
        display_on = False
        last_activity = None
        current_state_start = events[0]['timestamp']
        
        for i, event in enumerate(events):
            timestamp = event['timestamp']
            event_type = event['type']
            
            # Určit další timestamp
            next_timestamp = events[i+1]['timestamp'] if i+1 < len(events) else datetime.now()
            
            # Zpracovat event
            if event_type == 'boot':
                if i > 0:
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': 'shutdown',
                        'color': 'black'
                    })
                system_on = True
                display_on = True
                last_activity = timestamp
                current_state_start = timestamp
                
            elif event_type == 'shutdown':
                if system_on:
                    state = self._determine_state(display_on, last_activity, timestamp)
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': state,
                        'color': 'green' if state == 'active' else 'red'
                    })
                system_on = False
                display_on = False
                current_state_start = timestamp
                
            elif event_type == 'sleep':
                if system_on:
                    state = self._determine_state(display_on, last_activity, timestamp)
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': state,
                        'color': 'green' if state == 'active' else 'red'
                    })
                    current_state_start = timestamp
                    display_on = False
                    
            elif event_type in ['wake_full', 'wake_dark', 'wake']:
                if not display_on and system_on:
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': 'sleep',
                        'color': 'lightgray'
                    })
                    current_state_start = timestamp
                    
                if event_type == 'wake_full':
                    display_on = True
                    last_activity = timestamp
                    
            elif event_type == 'display_on':
                if not display_on and system_on:
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': 'inactive' if (timestamp - current_state_start).seconds < 3600 else 'sleep',
                        'color': 'red' if (timestamp - current_state_start).seconds < 3600 else 'lightgray'
                    })
                    current_state_start = timestamp
                display_on = True
                last_activity = timestamp
                
            elif event_type == 'display_off':
                if display_on and system_on:
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': 'active',
                        'color': 'green'
                    })
                    current_state_start = timestamp
                display_on = False
                
            # Kontrola neaktivity
            if display_on and last_activity and system_on:
                time_since_activity = (timestamp - last_activity).total_seconds()
                if time_since_activity > self.config.activity_threshold_seconds:
                    active_end = last_activity + timedelta(seconds=self.config.activity_threshold_seconds)
                    if active_end > current_state_start:
                        states.append({
                            'start': current_state_start,
                            'end': active_end,
                            'state': 'active',
                            'color': 'green'
                        })
                        current_state_start = active_end
                    last_activity = None
                    
        # Dokončit poslední stav
        if current_state_start < datetime.now():
            if not system_on:
                final_state = 'shutdown'
                color = 'black'
            elif display_on:
                final_state = self._determine_state(display_on, last_activity, datetime.now())
                color = 'green' if final_state == 'active' else 'red'
            else:
                final_state = 'sleep'
                color = 'lightgray'
                
            states.append({
                'start': current_state_start,
                'end': datetime.now(),
                'state': final_state,
                'color': color
            })
            
        return self._merge_adjacent_states(states)
        
    def _determine_state(self, display_on, last_activity, current_time):
        """Určit stav na základě display a času od poslední aktivity"""
        if not display_on:
            return 'inactive'
        if last_activity and (current_time - last_activity).total_seconds() > self.config.activity_threshold_seconds:
            return 'inactive'
        return 'active'
        
    def _merge_adjacent_states(self, states):
        """Sloučit sousední stavy stejného typu"""
        if not states:
            return states
            
        merged = []
        current = states[0]
        
        for state in states[1:]:
            if state['state'] == current['state'] and (state['start'] - current['end']).total_seconds() < 60:
                current['end'] = state['end']
            else:
                merged.append(current)
                current = state
                
        merged.append(current)
        return merged
        
    def update_all_displays(self):
        """Aktualizovat všechny displeje"""
        try:
            self.display_graph()
            self.generate_overview()
            self.analyze_applications()
            self.analyze_sleep_wake()
            self.generate_statistics()
            self.display_timeline()
            self.update_finance()
        except Exception as e:
            logging.error(f"Chyba při aktualizaci displejů: {str(e)}", exc_info=True)
            
    def display_graph(self):
        """Zobrazit graf aktivity"""
        try:
            self.ax.clear()
            
            if not self.states:
                self.ax.text(0.5, 0.5, 'Žádná data', ha='center', va='center')
                self.canvas.draw()
                return
                
            # Seskupit stavy podle dnů
            days = {}
            for state in self.states:
                day = state['start'].date()
                if day not in days:
                    days[day] = []
                days[day].append(state)
                
            # Vykreslit
            y_pos = 0
            y_labels = []
            
            for day in sorted(days.keys(), reverse=True)[:self.config.analysis_days]:
                day_states = days[day]
                y_labels.append(day.strftime('%Y-%m-%d\n%A'))
                
                for state in day_states:
                    start = mdates.date2num(state['start'])
                    end = mdates.date2num(state['end'])
                    width = end - start
                    
                    rect = Rectangle((start, y_pos - 0.4), width, 0.8,
                                   facecolor=state['color'],
                                   edgecolor='black',
                                   linewidth=0.5,
                                   picker=True)
                    rect.state_data = state
                    self.ax.add_patch(rect)
                    
                y_pos += 1
                
            # Nastavení os
            self.ax.set_ylim(-0.5, len(y_labels) - 0.5)
            self.ax.set_yticks(range(len(y_labels)))
            self.ax.set_yticklabels(y_labels)
            
            # X osa
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            
            # Legenda a popisky
            self.ax.grid(True, axis='x', alpha=0.3)
            self.ax.set_xlabel('Čas')
            self.ax.set_title('Mac Activity Timeline', fontsize=14, fontweight='bold')
            
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='green', edgecolor='black', label='Aktivní (<60s)'),
                Patch(facecolor='red', edgecolor='black', label='Neaktivní (>60s)'),
                Patch(facecolor='lightgray', edgecolor='black', label='Spánek'),
                Patch(facecolor='black', edgecolor='black', label='Vypnuto')
            ]
            self.ax.legend(handles=legend_elements, loc='upper right')
            
            # Event handler
            self.canvas.mpl_connect('button_press_event', self.on_click)
            
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            logging.error(f"Chyba při vykreslení grafu: {str(e)}", exc_info=True)
            
    def on_click(self, event):
        """Kliknutí na graf"""
        if event.inaxes != self.ax:
            return
            
        for child in self.ax.get_children():
            if isinstance(child, Rectangle) and hasattr(child, 'state_data'):
                if child.contains(event)[0]:
                    state = child.state_data
                    
                    info = f"Stav: {state['state'].upper()}\n"
                    info += f"Od: {state['start'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                    info += f"Do: {state['end'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    duration = (state['end'] - state['start']).total_seconds()
                    info += f"Trvání: {duration/60:.1f} minut ({duration/3600:.2f} hodin)\n"
                    
                    if state['state'] == 'active':
                        try:
                            value = (duration/3600) * float(self.hourly_rate_var.get())
                            info += f"Hodnota: {value:.2f} {self.config.currency}"
                        except ValueError:
                            pass
                        
                    self.info_text.delete('1.0', 'end')
                    self.info_text.insert('1.0', info)
                    break
                    
    def generate_overview(self):
        """Generate overview analysis"""
        try:
            self.overview_text.delete(1.0, tk.END)
            
            overview = "=== PŘEHLED SYSTÉMOVÉ AKTIVITY ===\n\n"
            
            # Count events
            overview += f"📊 SOUHRN UDÁLOSTÍ:\n"
            overview += f"  • Celkem restartů: {len(self.parsed_data['reboots'])}\n"
            overview += f"  • Celkem vypnutí: {len(self.parsed_data['shutdowns'])}\n"
            overview += f"  • Wake události: {len(self.parsed_data['wake_events'])}\n"
            overview += f"  • Sleep události: {len(self.parsed_data['sleep_events'])}\n"
            overview += f"  • Display události: {len(self.parsed_data['display_events'])}\n"
            overview += f"  • Aplikační události: {len(self.parsed_data['assertions'])}\n\n"
            
            # Recent activity
            overview += "📅 NEDÁVNÉ SYSTÉMOVÉ UDÁLOSTI:\n"
            if self.parsed_data['reboots']:
                last_reboot = self.parsed_data['reboots'][-1]
                overview += f"  • Poslední restart: {last_reboot['timestamp'].strftime('%Y-%m-%d %H:%M')}\n"
                
            if self.parsed_data['shutdowns']:
                last_shutdown = self.parsed_data['shutdowns'][-1]
                overview += f"  • Poslední vypnutí: {last_shutdown['timestamp'].strftime('%Y-%m-%d %H:%M')}\n"
                
            # Activity patterns
            if self.parsed_data['assertions']:
                overview += "\n⏰ VZORY AKTIVITY:\n"
                hours = defaultdict(int)
                for assertion in self.parsed_data['assertions']:
                    hours[assertion['timestamp'].hour] += 1
                    
                if hours:
                    peak_hour = max(hours.items(), key=lambda x: x[1])
                    overview += f"  • Nejaktivnější hodina: {peak_hour[0]:02d}:00 ({peak_hour[1]} událostí)\n"
                    
                    active_hours = sorted(hours.keys())
                    if active_hours:
                        overview += f"  • Rozsah aktivních hodin: {active_hours[0]:02d}:00 - {active_hours[-1]:02d}:00\n"
                        
            # Top applications
            if self.parsed_data['app_activity']:
                overview += "\n📱 TOP AKTIVNÍ APLIKACE:\n"
                app_counts = [(app, len(events)) for app, events in self.parsed_data['app_activity'].items()]
                app_counts.sort(key=lambda x: x[1], reverse=True)
                
                for i, (app, count) in enumerate(app_counts[:10], 1):
                    overview += f"  {i}. {app}: {count} událostí\n"
                    
            # Denní souhrn
            overview += "\n📈 DENNÍ AKTIVITA:\n"
            daily_active = defaultdict(float)
            for state in self.states:
                if state['state'] == 'active':
                    day = state['start'].date()
                    duration = (state['end'] - state['start']).total_seconds() / 3600
                    daily_active[day] += duration
                    
            for day in sorted(daily_active.keys(), reverse=True)[:7]:
                overview += f"  • {day.strftime('%Y-%m-%d (%A)')}: {daily_active[day]:.2f} hodin\n"
                
            self.overview_text.insert(tk.END, overview)
            
        except Exception as e:
            logging.error(f"Chyba při generování přehledu: {str(e)}", exc_info=True)
            self.overview_text.insert(tk.END, "Chyba při generování přehledu")
            
    def analyze_applications(self):
        """Analyze application activity"""
        try:
            # Clear axes
            self.app_pie_ax.clear()
            self.app_timeline_ax.clear()
            
            if not self.parsed_data['app_activity']:
                self.app_pie_ax.text(0.5, 0.5, 'Žádná data', ha='center', va='center')
                self.app_canvas.draw()
                return
                
            # Pie chart - top 10 apps
            app_counts = [(app, len(events)) for app, events in self.parsed_data['app_activity'].items()]
            app_counts.sort(key=lambda x: x[1], reverse=True)
            
            top_apps = app_counts[:10]
            labels = [app[0] for app in top_apps]
            sizes = [app[1] for app in top_apps]
            
            self.app_pie_ax.pie(sizes, labels=labels, autopct='%1.1f%%')
            self.app_pie_ax.set_title('Top 10 Aktivních Aplikací')
            
            # Timeline - aktivita aplikací v čase
            hour_app_activity = defaultdict(lambda: defaultdict(int))
            
            for app, events in self.parsed_data['app_activity'].items():
                if app in [a[0] for a in top_apps[:5]]:  # Jen top 5 pro přehlednost
                    for event in events:
                        hour = event['timestamp'].hour
                        hour_app_activity[hour][app] += 1
                        
            # Vykreslit timeline
            hours = list(range(24))
            bottom = [0] * 24
            
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
            for i, (app, _) in enumerate(top_apps[:5]):
                values = [hour_app_activity[h][app] for h in hours]
                self.app_timeline_ax.bar(hours, values, bottom=bottom, 
                                        label=app, color=colors[i % len(colors)])
                bottom = [b + v for b, v in zip(bottom, values)]
                
            self.app_timeline_ax.set_xlabel('Hodina')
            self.app_timeline_ax.set_ylabel('Počet událostí')
            self.app_timeline_ax.set_title('Aktivita Aplikací během dne')
            self.app_timeline_ax.legend()
            self.app_timeline_ax.set_xticks(hours)
            
            self.app_fig.tight_layout()
            self.app_canvas.draw()
            
            # Text details
            self.apps_text.delete(1.0, tk.END)
            
            apps_analysis = "=== DETAILNÍ ANALÝZA APLIKACÍ ===\n\n"
            
            for app, events in sorted(self.parsed_data['app_activity'].items(), 
                                     key=lambda x: len(x[1]), reverse=True)[:10]:
                apps_analysis += f"📱 {app}\n"
                apps_analysis += f"  Celkem událostí: {len(events)}\n"
                
                # Analyze event types
                event_types = Counter()
                for event in events:
                    if event.get('action'):
                        event_types[event['action']] += 1
                    
                if event_types:
                    apps_analysis += "  Typy událostí:\n"
                    for event_type, count in event_types.most_common(3):
                        apps_analysis += f"    • {event_type}: {count}\n"
                    
                apps_analysis += "\n"
                
            self.apps_text.insert(tk.END, apps_analysis)
            
        except Exception as e:
            logging.error(f"Chyba při analýze aplikací: {str(e)}", exc_info=True)
            
    def analyze_sleep_wake(self):
        """Analyze sleep/wake patterns"""
        try:
            self.sleep_ax.clear()
            
            # Calculate sleep durations
            sleep_durations = []
            wake_durations = []
            
            # Pair sleep and wake events
            events = []
            for s in self.parsed_data['sleep_events']:
                events.append((s['timestamp'], 'sleep', s))
            for w in self.parsed_data['wake_events']:
                events.append((w['timestamp'], 'wake', w))
                
            events.sort(key=lambda x: x[0])  # Sort by timestamp
            
            # Calculate durations
            for i in range(len(events)-1):
                curr_time = events[i][0]
                next_time = events[i+1][0]
                duration = next_time - curr_time
                
                if events[i][1] == 'sleep' and events[i+1][1] == 'wake':
                    sleep_durations.append(duration)
                elif events[i][1] == 'wake' and events[i+1][1] == 'sleep':
                    wake_durations.append(duration)
                    
            # Graf sleep/wake cyklů
            if sleep_durations or wake_durations:
                days = defaultdict(lambda: {'sleep': timedelta(), 'wake': timedelta()})
                
                for i in range(len(events)-1):
                    day = events[i][0].date()
                    duration = events[i+1][0] - events[i][0]
                    
                    if events[i][1] == 'sleep':
                        days[day]['sleep'] += duration
                    else:
                        days[day]['wake'] += duration
                        
                # Vykreslit graf
                sorted_days = sorted(days.keys())[-7:]  # Posledních 7 dní
                
                if sorted_days:
                    sleep_hours = [days[d]['sleep'].total_seconds()/3600 for d in sorted_days]
                    wake_hours = [days[d]['wake'].total_seconds()/3600 for d in sorted_days]
                    
                    x_pos = range(len(sorted_days))
                    width = 0.35
                    
                    self.sleep_ax.bar([p - width/2 for p in x_pos], sleep_hours, width, 
                                     label='Spánek', color='#7f8c8d')
                    self.sleep_ax.bar([p + width/2 for p in x_pos], wake_hours, width,
                                     label='Bdělý stav', color='#3498db')
                    
                    self.sleep_ax.set_xlabel('Den')
                    self.sleep_ax.set_ylabel('Hodiny')
                    self.sleep_ax.set_title('Sleep/Wake Cykly')
                    self.sleep_ax.set_xticks(x_pos)
                    self.sleep_ax.set_xticklabels([d.strftime('%m-%d') for d in sorted_days], rotation=45)
                    self.sleep_ax.legend()
                    
            self.sleep_fig.tight_layout()
            self.sleep_canvas.draw()
            
            # Text statistics
            self.sleep_text.delete(1.0, tk.END)
            
            sleep_analysis = "=== ANALÝZA SPÁNKU ===\n\n"
            
            if sleep_durations:
                sleep_analysis += "😴 STATISTIKY SPÁNKU:\n"
                avg_sleep = sum(sleep_durations, timedelta()) / len(sleep_durations)
                sleep_analysis += f"  • Průměrná doba spánku: {avg_sleep}\n"
                sleep_analysis += f"  • Nejdelší spánek: {max(sleep_durations)}\n"
                sleep_analysis += f"  • Nejkratší spánek: {min(sleep_durations)}\n"
                sleep_analysis += f"  • Celkem spánkových cyklů: {len(sleep_durations)}\n\n"
                
            if wake_durations:
                sleep_analysis += "☀️ STATISTIKY BDĚLOSTI:\n"
                avg_wake = sum(wake_durations, timedelta()) / len(wake_durations)
                sleep_analysis += f"  • Průměrná doba bdělosti: {avg_wake}\n"
                sleep_analysis += f"  • Nejdelší bdělost: {max(wake_durations)}\n"
                sleep_analysis += f"  • Nejkratší bdělost: {min(wake_durations)}\n\n"
                
            self.sleep_text.insert(tk.END, sleep_analysis)
            
        except Exception as e:
            logging.error(f"Chyba při analýze spánku: {str(e)}", exc_info=True)
            
    def generate_statistics(self):
        """Generate detailed statistics"""
        try:
            # Clear axes
            self.hour_ax.clear()
            self.day_ax.clear()
            
            # Hour-by-hour activity
            hour_counts = defaultdict(int)
            
            for event in self.all_events:
                hour_counts[event['timestamp'].hour] += 1
                
            # Hourly histogram
            hours = list(range(24))
            counts = [hour_counts[h] for h in hours]
            
            self.hour_ax.bar(hours, counts, color='#3498db')
            self.hour_ax.set_xlabel('Hodina')
            self.hour_ax.set_ylabel('Počet událostí')
            self.hour_ax.set_title('Aktivita během dne')
            self.hour_ax.set_xticks(hours)
            self.hour_ax.grid(True, alpha=0.3)
            
            # Day of week analysis
            weekday_counts = defaultdict(int)
            for event in self.all_events:
                weekday_counts[event['timestamp'].weekday()] += 1
                
            days = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']
            day_counts = [weekday_counts[i] for i in range(7)]
            
            self.day_ax.bar(days, day_counts, color='#e74c3c')
            self.day_ax.set_xlabel('Den v týdnu')
            self.day_ax.set_ylabel('Počet událostí')
            self.day_ax.set_title('Aktivita podle dnů v týdnu')
            self.day_ax.grid(True, alpha=0.3)
            
            self.stats_fig.tight_layout()
            self.stats_canvas.draw()
            
            # Text statistics
            self.stats_text.delete(1.0, tk.END)
            
            stats = "=== PODROBNÉ STATISTIKY ===\n\n"
            
            # Nejaktivnější hodiny
            if hour_counts:
                top_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                stats += "🕒 NEJAKTIVNĚJŠÍ HODINY:\n"
                for hour, count in top_hours:
                    stats += f"  • {hour:02d}:00 - {count} událostí\n"
                
            stats += "\n📊 CELKOVÉ METRIKY:\n"
            
            total_active_time = sum((state['end'] - state['start']).total_seconds() / 3600 
                                   for state in self.states if state['state'] == 'active')
            
            if self.states:
                unique_days = len(set(s['start'].date() for s in self.states))
                if unique_days > 0:
                    efficiency = (total_active_time / (24 * unique_days)) * 100
                    stats += f"  • Celková efektivita: {efficiency:.1f}%\n"
                    stats += f"  • Průměrná aktivní doba/den: {total_active_time / unique_days:.2f} hodin\n"
                
            self.stats_text.insert(tk.END, stats)
            
        except Exception as e:
            logging.error(f"Chyba při generování statistik: {str(e)}", exc_info=True)
            
    def display_timeline(self):
        """Display timeline visualization"""
        try:
            self.timeline_canvas.delete("all")
            self.timeline_text.delete(1.0, tk.END)
            
            # Get canvas dimensions
            self.timeline_canvas.update()
            width = self.timeline_canvas.winfo_width()
            height = self.timeline_canvas.winfo_height()
            
            if width < 100:
                return
                
            # Draw timeline for last 24 hours
            y_center = height // 2
            margin = 50
            
            # Main timeline
            self.timeline_canvas.create_line(margin, y_center, width-margin, y_center, 
                                            fill='gray', width=2)
            
            # Hour markers
            hours_to_show = 24
            hour_width = (width - 2*margin) / hours_to_show
            
            for i in range(hours_to_show + 1):
                x = margin + i * hour_width
                self.timeline_canvas.create_line(x, y_center-10, x, y_center+10, fill='gray')
                self.timeline_canvas.create_text(x, y_center+20, text=f"{i:02d}", anchor='n')
                
            # Plot recent events
            now = datetime.now()
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            for event in self.all_events:
                if event['timestamp'] >= day_start:
                    hours_from_start = (event['timestamp'] - day_start).total_seconds() / 3600
                    if hours_from_start <= hours_to_show:
                        x = margin + hours_from_start * hour_width
                        
                        # Color by type
                        if event['type'] == 'display_on':
                            color = '#27ae60'
                            y = y_center - 30
                        elif event['type'] == 'display_off':
                            color = '#e74c3c'
                            y = y_center - 30
                        elif event['type'] in ['sleep', 'wake_full', 'wake_dark']:
                            color = '#3498db'
                            y = y_center - 50
                        else:
                            color = '#95a5a6'
                            y = y_center - 70
                            
                        self.timeline_canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline='')
                        
            # Legend
            self.timeline_canvas.create_text(margin, 20, text="24-hodinový Timeline",
                                            anchor='w', font=('Arial', 12, 'bold'))
            
            legend_items = [
                ('Display On/Off', '#27ae60'),
                ('Sleep/Wake', '#3498db'),
                ('Ostatní', '#95a5a6')
            ]
            
            for i, (label, color) in enumerate(legend_items):
                x = width - margin - 150
                y = 30 + i * 20
                self.timeline_canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline='')
                self.timeline_canvas.create_text(x+10, y, text=label, anchor='w')
                
            # Timeline text
            timeline = "=== TIMELINE UDÁLOSTÍ (posledních 50) ===\n\n"
            
            for event in sorted(self.all_events, key=lambda x: x['timestamp'], reverse=True)[:50]:
                time_str = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                type_str = event['type'].ljust(15)
                desc = event.get('description', '')
                
                if event['category'] == 'display':
                    emoji = "🖥️"
                elif event['category'] == 'power':
                    emoji = "⚡"
                elif event['category'] == 'system':
                    emoji = "💻"
                else:
                    emoji = "📱"
                    
                timeline += f"{time_str} | {emoji} {type_str} | {desc}\n"
                
            self.timeline_text.insert(tk.END, timeline)
            
        except Exception as e:
            logging.error(f"Chyba při zobrazení timeline: {str(e)}", exc_info=True)
            
    def update_finance(self):
        """Update finance calculations"""
        try:
            self.finance_text.delete(1.0, tk.END)
            
            try:
                hourly_rate = float(self.hourly_rate_var.get())
            except:
                hourly_rate = self.config.default_hourly_rate
                
            finance = "=== FINANČNÍ ANALÝZA ===\n\n"
            
            # Calculate active hours per day
            daily_active = defaultdict(float)
            for state in self.states:
                if state['state'] == 'active':
                    day = state['start'].date()
                    duration = (state['end'] - state['start']).total_seconds() / 3600
                    daily_active[day] += duration
                    
            finance += f"💰 NASTAVENÍ:\n"
            finance += f"  • Hodinová sazba: {hourly_rate} {self.config.currency}/hod\n\n"
            
            finance += "📅 DENNÍ PŘEHLED:\n"
            total_hours = 0
            total_money = 0
            
            for day in sorted(daily_active.keys(), reverse=True):
                hours = daily_active[day]
                money = hours * hourly_rate
                
                finance += f"  {day.strftime('%Y-%m-%d (%A)')}: {hours:.2f}h = {money:,.2f} {self.config.currency}\n"
                
                total_hours += hours
                total_money += money
                
            finance += f"\n📊 CELKOVÝ SOUHRN:\n"
            finance += f"  • Celkem odpracováno: {total_hours:.2f} hodin\n"
            finance += f"  • Celková částka: {total_money:,.2f} {self.config.currency}\n"
            
            if daily_active:
                avg_daily = total_money / len(daily_active)
                finance += f"\n📈 PROJEKCE:\n"
                finance += f"  • Průměr na den: {avg_daily:,.2f} {self.config.currency}\n"
                finance += f"  • Projekce týden (5 dní): {avg_daily * 5:,.2f} {self.config.currency}\n"
                finance += f"  • Projekce měsíc (22 dní): {avg_daily * 22:,.2f} {self.config.currency}\n"
                
            self.finance_text.insert(tk.END, finance)
            
        except Exception as e:
            logging.error(f"Chyba při výpočtu financí: {str(e)}", exc_info=True)
            
    def show_settings(self):
        """Zobrazit nastavení aplikace"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Nastavení")
        settings_window.geometry("500x600")
        
        # Notebook pro kategorie nastavení
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Analýza
        analysis_frame = ttk.Frame(notebook)
        notebook.add(analysis_frame, text="Analýza")
        
        ttk.Label(analysis_frame, text="Počet dní k analýze:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        days_var = tk.StringVar(value=str(self.config.analysis_days))
        ttk.Entry(analysis_frame, textvariable=days_var, width=10).grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(analysis_frame, text="Práh aktivity (sekundy):").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        threshold_var = tk.StringVar(value=str(self.config.activity_threshold_seconds))
        ttk.Entry(analysis_frame, textvariable=threshold_var, width=10).grid(row=1, column=1, padx=10, pady=5)
        
        # Limity
        limits_frame = ttk.Frame(notebook)
        notebook.add(limits_frame, text="Limity")
        
        ttk.Label(limits_frame, text="Max. počet eventů:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        events_var = tk.StringVar(value=str(self.config.max_events))
        ttk.Entry(limits_frame, textvariable=events_var, width=10).grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(limits_frame, text="Limit paměti (MB):").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        memory_var = tk.StringVar(value=str(self.config.memory_limit_mb))
        ttk.Entry(limits_frame, textvariable=memory_var, width=10).grid(row=1, column=1, padx=10, pady=5)
        
        # Tlačítka
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='x', pady=10)
        
        def save_settings():
            try:
                self.config.analysis_days = int(days_var.get())
                self.config.activity_threshold_seconds = int(threshold_var.get())
                self.config.max_events = int(events_var.get())
                self.config.memory_limit_mb = int(memory_var.get())
                
                self.config.validate()
                
                messagebox.showinfo("Nastavení", "Nastavení bylo uloženo. Obnovte analýzu pro aplikaci změn.")
                settings_window.destroy()
                
            except (ValueError, ValidationError) as e:
                messagebox.showerror("Chyba", f"Neplatné nastavení: {str(e)}")
                
        ttk.Button(button_frame, text="Uložit", command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Zrušit", command=settings_window.destroy).pack(side='left', padx=5)
        
    def export_data(self):
        """Export data to file - BEZPEČNÁ VERZE"""
        filename = filedialog.asksaveasfilename(
            title="Uložit report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Validace cesty
                file_path = Path(filename)
                if not file_path.suffix in self.config.export_formats + ['.txt']:
                    raise ValidationError(f"Nepodporovaný formát souboru: {file_path.suffix}")
                    
                # Kontrola velikosti dat
                if len(self.all_events) > self.config.max_events:
                    if not messagebox.askyesno("Varování", 
                        f"Export obsahuje {len(self.all_events)} eventů. Chcete pokračovat?"):
                        return
                        
                if filename.endswith('.json'):
                    # Export as JSON
                    export_data = {
                        'metadata': {
                            'exported_at': datetime.now().isoformat(),
                            'version': '2.0',
                            'events_count': len(self.all_events),
                            'states_count': len(self.states)
                        },
                        'events': [
                            {
                                'timestamp': e['timestamp'].isoformat(),
                                'type': e['type'],
                                'category': e.get('category', ''),
                                'description': e.get('description', '')
                            }
                            for e in self.all_events
                        ],
                        'states': [
                            {
                                'start': s['start'].isoformat(),
                                'end': s['end'].isoformat(),
                                'state': s['state']
                            }
                            for s in self.states
                        ]
                    }
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                        
                elif filename.endswith('.csv'):
                    # Export as CSV
                    import csv
                    
                    with open(filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        
                        # Header
                        writer.writerow(['Timestamp', 'Type', 'Category', 'Description'])
                        
                        # Data
                        for event in self.all_events:
                            writer.writerow([
                                event['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                event['type'],
                                event.get('category', ''),
                                event.get('description', '')
                            ])
                            
                else:
                    # Export as text
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("MAC ACTIVITY REPORT - SECURE VERSION\n")
                        f.write("="*80 + "\n\n")
                        
                        f.write("PŘEHLED\n")
                        f.write("-"*40 + "\n")
                        f.write(self.overview_text.get(1.0, tk.END))
                        
                        f.write("\n\nFINANCE\n")
                        f.write("-"*40 + "\n")
                        f.write(self.finance_text.get(1.0, tk.END))
                        
                        f.write("\n\nTIMELINE\n")
                        f.write("-"*40 + "\n")
                        f.write(self.timeline_text.get(1.0, tk.END))
                        
                messagebox.showinfo("Export", f"Data byla bezpečně exportována do:\n{filename}")
                logging.info(f"Data exportována do: {filename}")
                
            except Exception as e:
                logging.error(f"Chyba při exportu: {str(e)}", exc_info=True)
                messagebox.showerror("Chyba", f"Nepodařilo se exportovat data:\n{str(e)}")
                
    def load_from_file(self):
        """Load data from file - BEZPEČNÁ VERZE"""
        filename = filedialog.askopenfilename(
            title="Načíst soubor",
            filetypes=[("JSON files", "*.json"), ("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                file_path = Path(filename)
                
                # Kontrola velikosti souboru
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > self.config.max_file_size_mb:
                    raise ValidationError(f"Soubor je příliš velký ({file_size_mb:.1f} MB). "
                                        f"Maximum je {self.config.max_file_size_mb} MB.")
                    
                if filename.endswith('.json'):
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # Validace struktury
                    if 'events' not in data:
                        raise ValidationError("Neplatný formát souboru - chybí 'events'")
                        
                    # Načíst eventy
                    self.all_events = []
                    for event_data in data['events'][:self.config.max_events]:
                        try:
                            self.all_events.append({
                                'timestamp': datetime.fromisoformat(event_data['timestamp']),
                                'type': event_data['type'],
                                'category': event_data.get('category', ''),
                                'description': event_data.get('description', '')
                            })
                        except Exception as e:
                            logging.warning(f"Nelze načíst event: {e}")
                            
                    # Seřadit podle času
                    self.all_events.sort(key=lambda x: x['timestamp'])
                    
                    # Aktualizovat displeje
                    self.update_all_displays()
                    
                    messagebox.showinfo("Načteno", 
                        f"Úspěšně načteno {len(self.all_events)} eventů")
                    
                else:
                    messagebox.showinfo("Info", 
                        "Načítání tohoto formátu souboru není zatím podporováno")
                    
            except Exception as e:
                logging.error(f"Chyba při načítání souboru: {str(e)}", exc_info=True)
                messagebox.showerror("Chyba", f"Nepodařilo se načíst soubor:\n{str(e)}")


def main():
    """Hlavní funkce aplikace"""
    root = tk.Tk()
    
    # Nastavit ikonu a téma
    root.option_add('*tearOff', False)
    
    # Vytvořit aplikaci
    app = MacActivityAdvancedSecure(root)
    
    # Spustit hlavní smyčku
    root.mainloop()


if __name__ == "__main__":
    main()