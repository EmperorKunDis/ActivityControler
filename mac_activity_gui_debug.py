#!/usr/bin/env python3
"""
MacMini Activity Analyzer GUI - Debug Version
Interaktivní desktop aplikace pro analýzu aktivity Mac počítače s rozšířeným debugováním
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import re
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
from typing import List, Dict
import threading
import queue
import logging
import sys
import os
import traceback

# Nastavení loggingu
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('activity_analyzer_debug.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

class MacActivityGUI:
    """Hlavní třída aplikace"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("MacMini Activity Analyzer - Debug Version")
        self.root.geometry("1400x900")
        
        logger.info("="*50)
        logger.info("Starting MacMini Activity Analyzer")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info("="*50)
        
        # Nastavení pro high DPI displays (Apple Silicon Macs)
        try:
            self.root.tk.call('tk', 'scaling', 2.0)
            logger.debug("Display scaling set to 2.0")
        except Exception as e:
            logger.warning(f"Could not set display scaling: {e}")
            
        # Datové struktury
        self.events = []
        self.states = []
        self.daily_stats = {}
        
        # Threading
        self.queue = queue.Queue()
        self.analysis_thread = None
        
        # GUI setup
        self.setup_gui()
        
        # Automaticky spustit analýzu
        self.root.after(100, self.start_analysis)
        logger.info("GUI initialization complete")
        
    def setup_gui(self):
        """Vytvořit GUI komponenty"""
        logger.debug("Setting up GUI components")
        
        # Hlavní frame s taby
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Graf
        self.graph_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text='Graf aktivity')
        self.setup_graph_tab()
        
        # Tab 2: Statistiky
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text='Statistiky')
        self.setup_stats_tab()
        
        # Tab 3: Finance
        self.finance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.finance_frame, text='Finanční přehled')
        self.setup_finance_tab()
        
        # Tab 4: Raw data
        self.raw_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_frame, text='Raw data')
        self.setup_raw_tab()
        
        # Tab 5: Debug Log
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text='Debug Log')
        self.setup_debug_tab()
        
        # Status bar
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side='bottom', fill='x', padx=5, pady=2)
        
        self.status_label = ttk.Label(self.status_frame, text='Připraven')
        self.status_label.pack(side='left')
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.status_frame, 
            length=200, 
            variable=self.progress_var
        )
        self.progress_bar.pack(side='right', padx=5)
        
        # Refresh button
        self.refresh_btn = ttk.Button(
            self.status_frame,
            text='🔄 Obnovit',
            command=self.start_analysis
        )
        self.refresh_btn.pack(side='right', padx=5)
        
        # Periodické aktualizace
        self.root.after(100, self.process_queue)
        
    def setup_graph_tab(self):
        """Nastavit tab s grafem"""
        # Matplotlib figure
        self.fig = plt.Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Info panel
        self.info_frame = ttk.LabelFrame(self.graph_frame, text='Informace o vybraném úseku')
        self.info_frame.pack(fill='x', padx=5, pady=5)
        
        self.info_text = scrolledtext.ScrolledText(
            self.info_frame,
            height=6,
            width=80,
            wrap='word'
        )
        self.info_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def setup_stats_tab(self):
        """Nastavit tab se statistikami"""
        # Treeview pro statistiky
        self.stats_tree = ttk.Treeview(
            self.stats_frame,
            columns=('datum', 'start', 'konec', 'aktivni', 'pauzy', 'celkem'),
            show='tree headings'
        )
        
        self.stats_tree.heading('#0', text='Den')
        self.stats_tree.heading('datum', text='Datum')
        self.stats_tree.heading('start', text='První aktivita')
        self.stats_tree.heading('konec', text='Poslední aktivita')
        self.stats_tree.heading('aktivni', text='Aktivní čas')
        self.stats_tree.heading('pauzy', text='Pauzy')
        self.stats_tree.heading('celkem', text='Celkem')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.stats_frame, orient='vertical', command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=scrollbar.set)
        
        self.stats_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Summary frame
        self.summary_frame = ttk.LabelFrame(self.stats_frame, text='Celkový souhrn')
        self.summary_frame.pack(fill='x', padx=5, pady=5)
        
        self.summary_label = ttk.Label(self.summary_frame, text='Čekám na data...')
        self.summary_label.pack(padx=10, pady=10)
        
    def setup_finance_tab(self):
        """Nastavit tab s financemi"""
        # Nastavení hodinové sazby
        rate_frame = ttk.Frame(self.finance_frame)
        rate_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(rate_frame, text='Hodinová sazba (Kč):').pack(side='left', padx=5)
        
        self.hourly_rate_var = tk.StringVar(value='250')
        rate_entry = ttk.Entry(rate_frame, textvariable=self.hourly_rate_var, width=10)
        rate_entry.pack(side='left', padx=5)
        
        ttk.Button(
            rate_frame, 
            text='Přepočítat',
            command=self.recalculate_finance
        ).pack(side='left', padx=5)
        
        # Finance text
        self.finance_text = scrolledtext.ScrolledText(
            self.finance_frame,
            height=20,
            width=80,
            wrap='word'
        )
        self.finance_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Export button
        ttk.Button(
            self.finance_frame,
            text='📄 Exportovat report (HTML)',
            command=self.export_report
        ).pack(pady=10)
        
    def setup_raw_tab(self):
        """Nastavit tab s raw daty"""
        self.raw_text = scrolledtext.ScrolledText(
            self.raw_frame,
            height=30,
            width=100,
            wrap='word',
            font=('Courier', 10)
        )
        self.raw_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def setup_debug_tab(self):
        """Nastavit tab s debug logem"""
        self.debug_text = scrolledtext.ScrolledText(
            self.debug_frame,
            height=30,
            width=100,
            wrap='word',
            font=('Courier', 9),
            bg='black',
            fg='white'
        )
        self.debug_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tlačítko pro načtení logu
        ttk.Button(
            self.debug_frame,
            text='🔄 Načíst aktuální log',
            command=self.load_debug_log
        ).pack(pady=5)
        
    def load_debug_log(self):
        """Načíst a zobrazit debug log"""
        try:
            with open('activity_analyzer_debug.log', 'r') as f:
                content = f.read()
                self.debug_text.delete('1.0', 'end')
                self.debug_text.insert('1.0', content)
                self.debug_text.see('end')
        except Exception as e:
            self.debug_text.insert('end', f"\nChyba při načítání logu: {e}\n")
            
    def start_analysis(self):
        """Spustit analýzu v novém vlákně"""
        if self.analysis_thread and self.analysis_thread.is_alive():
            logger.warning("Analysis already in progress")
            messagebox.showwarning("Upozornění", "Analýza již probíhá")
            return
            
        logger.info("Starting new analysis thread")
        self.analysis_thread = threading.Thread(target=self.analyze_activity, daemon=True)
        self.analysis_thread.start()
        
    def process_queue(self):
        """Zpracovat zprávy z fronty"""
        try:
            while True:
                msg = self.queue.get_nowait()
                msg_type = msg.get('type')
                
                if msg_type == 'status':
                    self.status_label.config(text=msg['text'])
                    logger.debug(f"Status update: {msg['text']}")
                elif msg_type == 'progress':
                    self.progress_var.set(msg['value'])
                elif msg_type == 'graph':
                    self.update_graph(msg['states'])
                elif msg_type == 'stats':
                    self.update_stats(msg['stats'])
                elif msg_type == 'finance':
                    self.update_finance(msg['data'])
                elif msg_type == 'raw':
                    self.update_raw_data(msg['events'])
                elif msg_type == 'error':
                    error_msg = msg['text']
                    logger.error(f"Error in analysis: {error_msg}")
                    messagebox.showerror("Chyba", error_msg)
                elif msg_type == 'done':
                    self.status_label.config(text="Analýza dokončena")
                    self.progress_var.set(0)
                    logger.info("Analysis completed successfully")
                    self.load_debug_log()  # Automaticky načíst log po dokončení
                    
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)
            
    def analyze_activity(self):
        """Analyzovat aktivitu v pozadí"""
        try:
            logger.info("Starting activity analysis")
            # Získat eventy
            self.queue.put({'type': 'status', 'text': 'Načítám systémové logy...'})
            self.queue.put({'type': 'progress', 'value': 20})
            
            # Získat sleep/wake eventy
            logger.debug("Getting pmset events")
            pmset_events = self.get_pmset_events()
            logger.info(f"Found {len(pmset_events)} pmset events")
            
            # Získat reboot eventy
            logger.debug("Getting reboot events")
            reboot_events = self.get_reboot_events()
            logger.info(f"Found {len(reboot_events)} reboot events")
            
            # Zkombinovat eventy
            self.events = sorted(pmset_events + reboot_events, key=lambda x: x['timestamp'])
            logger.info(f"Total events to analyze: {len(self.events)}")
            
            if not self.events:
                raise Exception("Žádné události k analýze. Zkontrolujte oprávnění pro Terminal.")
            
            # Odeslat raw data
            self.queue.put({'type': 'raw', 'events': self.events})
            
            # Analyzovat stavy
            self.queue.put({'type': 'status', 'text': 'Analyzuji aktivitu...'})
            self.queue.put({'type': 'progress', 'value': 60})
            
            self.states = self.analyze_states(self.events)
            logger.info(f"Analyzed {len(self.states)} states")
            
            # Počítat statistiky
            self.queue.put({'type': 'status', 'text': 'Počítám statistiky...'})
            self.queue.put({'type': 'progress', 'value': 80})
            
            daily_stats = self.calculate_daily_stats(self.states)
            
            # Odeslat výsledky
            self.queue.put({'type': 'graph', 'states': self.states})
            self.queue.put({'type': 'stats', 'stats': daily_stats})
            self.queue.put({'type': 'finance', 'data': {
                'states': self.states,
                'daily_stats': daily_stats
            }})
            
            self.queue.put({'type': 'done'})
            
        except Exception as e:
            error_msg = f"Chyba při analýze: {str(e)}"
            logger.exception("Error in analyze_activity")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.queue.put({'type': 'error', 'text': error_msg})
            self.queue.put({'type': 'done'})
            
    def run_command(self, command):
        """Spustit shell příkaz a vrátit výstup"""
        try:
            logger.debug(f"Running command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"Command failed with return code {result.returncode}")
                logger.warning(f"stderr: {result.stderr}")
                
            logger.debug(f"Command output length: {len(result.stdout)} chars")
            return result.stdout
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return ""
        except Exception as e:
            logger.error(f"Failed to run command '{command}': {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ""
            
    def get_pmset_events(self) -> List[Dict]:
        """Získat sleep/wake eventy z pmset"""
        events = []
        
        # Získat pmset log
        cmd = "pmset -g log | grep -E '(Sleep|Wake|Start)' | tail -1000"
        output = self.run_command(cmd)
        
        if not output:
            logger.warning("No output from pmset command")
            return events
            
        lines = output.strip().split('\n')
        logger.debug(f"Processing {len(lines)} pmset lines")
        
        for line in lines:
            if not line.strip():
                continue
                
            # Parsovat řádek
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
                
            try:
                # Parsovat timestamp
                timestamp = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S %z')
                
                # Kontrola rozsahu dat (posledních 10 dní)
                if timestamp < datetime.now(timestamp.tzinfo) - timedelta(days=10):
                    continue
                    
                event_type = self.get_event_type(line)
                if event_type:
                    events.append({
                        'timestamp': timestamp,
                        'type': event_type,
                        'raw': line.strip()
                    })
                    
            except Exception as e:
                logger.debug(f"Failed to parse pmset line: {line.strip()[:50]}... - Error: {e}")
                continue
                
        return events
        
    def get_event_type(self, line):
        """Určit typ eventu z pmset logu"""
        if 'Sleep' in line:
            return 'sleep'
        elif 'Wake' in line:
            return 'wake'
        elif 'Start' in line:
            return 'start'
        else:
            return None
            
    def get_reboot_events(self) -> List[Dict]:
        """Získat reboot eventy"""
        events = []
        
        # Získat reboot časy
        output = self.run_command("last reboot | head -20")
        
        if not output:
            logger.warning("No output from last reboot command")
            return events
            
        lines = output.strip().split('\n')
        logger.debug(f"Processing {len(lines)} reboot lines")
        
        for line in lines:
            if 'reboot' in line:
                # Parsovat datum
                match = re.search(r'reboot\s+~?\s+(.+)', line)
                if match:
                    date_str = match.group(1).strip()
                    try:
                        # Parsovat různé formáty
                        timestamp = None
                        
                        # Formát: "Mon Jan 1 12:00"
                        try:
                            timestamp = datetime.strptime(date_str, '%a %b %d %H:%M')
                            timestamp = timestamp.replace(year=datetime.now().year)
                        except:
                            pass
                            
                        if not timestamp:
                            # Formát: "Mon Jan 1 12:00:00 2023"
                            try:
                                timestamp = datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y')
                            except:
                                pass
                                
                        if timestamp:
                            # Přidat timezone
                            timestamp = timestamp.replace(tzinfo=datetime.now().astimezone().tzinfo)
                            
                            # Kontrola rozsahu
                            if timestamp > datetime.now().astimezone() - timedelta(days=10):
                                events.append({
                                    'timestamp': timestamp,
                                    'type': 'boot',
                                    'raw': line.strip()
                                })
                                
                    except Exception as e:
                        logger.debug(f"Failed to parse reboot line: {line.strip()} - Error: {e}")
                        
        # Získat shutdown časy
        output = self.run_command("last shutdown | head -20")
        
        if output:
            lines = output.strip().split('\n')
            logger.debug(f"Processing {len(lines)} shutdown lines")
            
            for line in lines:
                if 'shutdown' in line:
                    # Podobné parsování jako u reboot
                    match = re.search(r'shutdown\s+~?\s+(.+)', line)
                    if match:
                        date_str = match.group(1).strip()
                        try:
                            # ... parsování data ...
                            pass  # Implementace podobná jako výše
                        except:
                            continue
                            
        return events
        
    def analyze_states(self, events):
        """Analyzovat stavy z eventů"""
        states = []
        
        if not events:
            logger.warning("No events to analyze")
            return states
            
        # Seřadit eventy podle času
        events = sorted(events, key=lambda x: x['timestamp'])
        logger.debug(f"Analyzing {len(events)} events")
        
        # Přidat počáteční shutdown stav
        first_event = events[0]
        if first_event['type'] != 'boot':
            states.append({
                'start': first_event['timestamp'] - timedelta(hours=1),
                'end': first_event['timestamp'],
                'type': 'shutdown',
                'duration': timedelta(hours=1)
            })
            
        # Analyzovat eventy
        i = 0
        while i < len(events):
            current = events[i]
            
            if current['type'] == 'boot':
                # Po bootu je systém aktivní
                start = current['timestamp']
                
                # Najít další event
                end = None
                next_type = None
                
                if i + 1 < len(events):
                    next_event = events[i + 1]
                    end = next_event['timestamp']
                    next_type = next_event['type']
                else:
                    # Poslední event - předpokládáme aktivitu do teď
                    end = datetime.now().astimezone()
                    next_type = 'active'
                    
                # Rozdělit období na aktivní/neaktivní části
                if next_type == 'sleep':
                    # Aktivní až do sleep
                    states.append({
                        'start': start,
                        'end': end,
                        'type': 'active',
                        'duration': end - start
                    })
                elif next_type == 'shutdown':
                    # Aktivní až do shutdown
                    states.append({
                        'start': start,
                        'end': end,
                        'type': 'active',
                        'duration': end - start
                    })
                else:
                    # Analyzovat aktivitu podle času mezi eventy
                    self.analyze_active_period(states, start, end)
                    
            elif current['type'] == 'wake':
                # Po probuzení je systém aktivní
                start = current['timestamp']
                
                # Najít další event
                if i + 1 < len(events):
                    next_event = events[i + 1]
                    end = next_event['timestamp']
                    
                    if next_event['type'] == 'sleep':
                        # Analyzovat aktivitu mezi wake a sleep
                        self.analyze_active_period(states, start, end)
                    elif next_event['type'] == 'shutdown':
                        # Aktivní až do shutdown
                        states.append({
                            'start': start,
                            'end': end,
                            'type': 'active',
                            'duration': end - start
                        })
                else:
                    # Poslední event
                    end = datetime.now().astimezone()
                    self.analyze_active_period(states, start, end)
                    
            elif current['type'] == 'sleep':
                # Sleep stav
                start = current['timestamp']
                
                # Najít wake nebo boot
                end = start + timedelta(hours=8)  # Default 8 hodin spánku
                
                if i + 1 < len(events):
                    next_event = events[i + 1]
                    if next_event['type'] in ['wake', 'boot']:
                        end = next_event['timestamp']
                        
                states.append({
                    'start': start,
                    'end': end,
                    'type': 'sleep',
                    'duration': end - start
                })
                
            elif current['type'] == 'shutdown':
                # Shutdown stav
                start = current['timestamp']
                
                # Najít boot
                end = start + timedelta(hours=8)  # Default 8 hodin
                
                if i + 1 < len(events):
                    next_event = events[i + 1]
                    if next_event['type'] == 'boot':
                        end = next_event['timestamp']
                        
                states.append({
                    'start': start,
                    'end': end,
                    'type': 'shutdown',
                    'duration': end - start
                })
                
            i += 1
            
        logger.info(f"Created {len(states)} states")
        return states
        
    def analyze_active_period(self, states, start, end):
        """Analyzovat aktivní období a rozdělit na aktivní/pauzy"""
        # Pro zjednodušení - považujeme celé období za aktivní
        # V reálné aplikaci bychom zde analyzovali user activity
        
        duration = end - start
        
        if duration > timedelta(hours=8):
            # Dlouhé období - rozdělit na části
            current = start
            while current < end:
                segment_end = min(current + timedelta(hours=2), end)
                
                states.append({
                    'start': current,
                    'end': segment_end,
                    'type': 'active' if (segment_end - current) < timedelta(hours=1) else 'pause',
                    'duration': segment_end - current
                })
                
                current = segment_end
        else:
            # Krátké období - celé aktivní
            states.append({
                'start': start,
                'end': end,
                'type': 'active',
                'duration': duration
            })
            
    def calculate_daily_stats(self, states):
        """Vypočítat denní statistiky"""
        daily_stats = {}
        
        for state in states:
            date = state['start'].date()
            
            if date not in daily_stats:
                daily_stats[date] = {
                    'date': date,
                    'first_activity': state['start'],
                    'last_activity': state['end'],
                    'active_time': timedelta(),
                    'pause_time': timedelta(),
                    'sleep_time': timedelta(),
                    'shutdown_time': timedelta(),
                    'total_time': timedelta()
                }
                
            stats = daily_stats[date]
            
            # Update first/last activity
            if state['start'] < stats['first_activity']:
                stats['first_activity'] = state['start']
            if state['end'] > stats['last_activity']:
                stats['last_activity'] = state['end']
                
            # Add time to appropriate category
            if state['type'] == 'active':
                stats['active_time'] += state['duration']
            elif state['type'] == 'pause':
                stats['pause_time'] += state['duration']
            elif state['type'] == 'sleep':
                stats['sleep_time'] += state['duration']
            elif state['type'] == 'shutdown':
                stats['shutdown_time'] += state['duration']
                
            stats['total_time'] = stats['last_activity'] - stats['first_activity']
            
        logger.info(f"Calculated stats for {len(daily_stats)} days")
        return daily_stats
        
    def update_graph(self, states):
        """Aktualizovat graf"""
        logger.debug(f"Updating graph with {len(states)} states")
        
        self.ax.clear()
        
        if not states:
            self.ax.text(0.5, 0.5, 'Žádná data k zobrazení', 
                        transform=self.ax.transAxes,
                        ha='center', va='center')
            self.canvas.draw()
            return
            
        # Barvy pro různé stavy
        colors = {
            'active': '#00ff00',
            'pause': '#ff0000',
            'sleep': '#cccccc',
            'shutdown': '#000000'
        }
        
        # Vykreslit stavy
        for state in states:
            color = colors.get(state['type'], '#666666')
            
            self.ax.barh(
                0,
                mdates.date2num(state['end']) - mdates.date2num(state['start']),
                left=mdates.date2num(state['start']),
                height=0.8,
                color=color,
                edgecolor='black',
                linewidth=0.5
            )
            
        # Nastavení grafu
        self.ax.set_ylim(-0.5, 0.5)
        self.ax.set_xlabel('Čas')
        self.ax.set_title('Timeline aktivity počítače')
        
        # Formátování času na x-ose
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        self.fig.autofmt_xdate()
        
        # Legenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#00ff00', label='Aktivní'),
            Patch(facecolor='#ff0000', label='Pauza'),
            Patch(facecolor='#cccccc', label='Spánek'),
            Patch(facecolor='#000000', label='Vypnuto')
        ]
        self.ax.legend(handles=legend_elements, loc='upper right')
        
        # Odstranit y-osu
        self.ax.yaxis.set_visible(False)
        
        # Připojit click handler
        self.canvas.mpl_connect('button_press_event', self.on_graph_click)
        
        self.canvas.draw()
        
    def on_graph_click(self, event):
        """Handler pro kliknutí na graf"""
        if event.inaxes != self.ax:
            return
            
        # Převést x-souřadnici na datetime
        try:
            clicked_time = mdates.num2date(event.xdata)
            logger.debug(f"Graph clicked at time: {clicked_time}")
            
            # Najít odpovídající stav
            for state in self.states:
                if state['start'] <= clicked_time <= state['end']:
                    self.show_state_info(state)
                    break
                    
        except Exception as e:
            logger.error(f"Error handling graph click: {e}")
            
    def show_state_info(self, state):
        """Zobrazit informace o stavu"""
        info = f"Typ: {state['type'].upper()}\n"
        info += f"Start: {state['start'].strftime('%d.%m.%Y %H:%M:%S')}\n"
        info += f"Konec: {state['end'].strftime('%d.%m.%Y %H:%M:%S')}\n"
        info += f"Trvání: {state['duration']}\n"
        
        # Přidat finanční informace pro aktivní stavy
        if state['type'] == 'active':
            hours = state['duration'].total_seconds() / 3600
            try:
                hourly_rate = float(self.hourly_rate_var.get())
                cost = hours * hourly_rate
                info += f"\nHodin: {hours:.2f}\n"
                info += f"Hodnota: {cost:.2f} Kč"
            except:
                pass
                
        self.info_text.delete('1.0', 'end')
        self.info_text.insert('1.0', info)
        
    def update_stats(self, stats):
        """Aktualizovat statistiky"""
        logger.debug(f"Updating stats for {len(stats)} days")
        
        # Vyčistit treeview
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
            
        # Seřadit podle data
        sorted_dates = sorted(stats.keys(), reverse=True)
        
        total_active = timedelta()
        total_pause = timedelta()
        
        for date in sorted_dates:
            stat = stats[date]
            
            day_name = date.strftime('%A')
            date_str = date.strftime('%d.%m.%Y')
            start_str = stat['first_activity'].strftime('%H:%M')
            end_str = stat['last_activity'].strftime('%H:%M')
            
            active_str = self.format_duration(stat['active_time'])
            pause_str = self.format_duration(stat['pause_time'])
            total_str = self.format_duration(stat['total_time'])
            
            self.stats_tree.insert(
                '', 'end',
                text=day_name,
                values=(date_str, start_str, end_str, active_str, pause_str, total_str)
            )
            
            total_active += stat['active_time']
            total_pause += stat['pause_time']
            
        # Aktualizovat souhrn
        summary = f"Celkem aktivní: {self.format_duration(total_active)}\n"
        summary += f"Celkem pauzy: {self.format_duration(total_pause)}\n"
        summary += f"Průměrně aktivní za den: {self.format_duration(total_active / len(stats))}"
        
        self.summary_label.config(text=summary)
        
    def update_finance(self, data):
        """Aktualizovat finanční přehled"""
        try:
            logger.debug("Updating finance tab")
            
            states = data['states']
            daily_stats = data['daily_stats']
            
            # Získat hodinovou sazbu
            try:
                hourly_rate = float(self.hourly_rate_var.get())
            except:
                hourly_rate = 250
                self.hourly_rate_var.set("250")
                
            # Vypočítat celkové hodiny
            total_active_time = timedelta()
            for stat in daily_stats.values():
                total_active_time += stat['active_time']
                
            total_hours = total_active_time.total_seconds() / 3600
            total_cost = total_hours * hourly_rate
            
            # Vytvořit report
            report = "=" * 50 + "\n"
            report += "FINANČNÍ REPORT - AKTIVITA POČÍTAČE\n"
            report += "=" * 50 + "\n\n"
            
            report += f"Období: {min(daily_stats.keys()).strftime('%d.%m.%Y')} - {max(daily_stats.keys()).strftime('%d.%m.%Y')}\n"
            report += f"Hodinová sazba: {hourly_rate:.0f} Kč/hod\n"
            report += f"Počet analyzovaných dní: {len(daily_stats)}\n\n"
            
            report += "-" * 50 + "\n"
            report += "CELKOVÝ SOUHRN\n"
            report += "-" * 50 + "\n"
            report += f"Celkem aktivních hodin: {total_hours:.2f}\n"
            report += f"Celková částka: {total_cost:,.2f} Kč\n\n"
            
            report += "-" * 50 + "\n"
            report += "DENNÍ ROZPIS\n"
            report += "-" * 50 + "\n\n"
            
            # Denní rozpis
            for date in sorted(daily_stats.keys(), reverse=True):
                stat = daily_stats[date]
                hours = stat['active_time'].total_seconds() / 3600
                cost = hours * hourly_rate
                
                report += f"{date.strftime('%d.%m.%Y (%A)')}\n"
                report += f"  Aktivní čas: {self.format_duration(stat['active_time'])}\n"
                report += f"  Hodin: {hours:.2f}\n"
                report += f"  Částka: {cost:,.2f} Kč\n\n"
                
            # Projekce
            if len(daily_stats) > 0:
                avg_hours_per_day = total_hours / len(daily_stats)
                
                report += "-" * 50 + "\n"
                report += "PROJEKCE\n"
                report += "-" * 50 + "\n"
                report += f"Průměr hodin/den: {avg_hours_per_day:.2f}\n"
                report += f"Projekce týden (5 dní): {avg_hours_per_day * 5:.2f} hodin = {avg_hours_per_day * 5 * hourly_rate:,.2f} Kč\n"
                report += f"Projekce měsíc (20 dní): {avg_hours_per_day * 20:.2f} hodin = {avg_hours_per_day * 20 * hourly_rate:,.2f} Kč\n"
                
            self.finance_text.delete('1.0', 'end')
            self.finance_text.insert('1.0', report)
            
        except Exception as e:
            logger.error(f"Error updating finance: {e}")
            logger.error(traceback.format_exc())
            
    def update_raw_data(self, events):
        """Aktualizovat raw data"""
        logger.debug(f"Updating raw data with {len(events)} events")
        
        self.raw_text.delete('1.0', 'end')
        
        text = f"Celkem nalezeno {len(events)} událostí\n"
        text += "=" * 80 + "\n\n"
        
        for event in sorted(events, key=lambda x: x['timestamp'], reverse=True):
            text += f"{event['timestamp'].strftime('%d.%m.%Y %H:%M:%S')} - {event['type'].upper()}\n"
            text += f"  {event['raw']}\n\n"
            
        self.raw_text.insert('1.0', text)
        
    def format_duration(self, duration):
        """Formátovat timedelta na čitelný string"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        return f"{hours}h {minutes}m"
        
    def recalculate_finance(self):
        """Přepočítat finance s novou sazbou"""
        try:
            hourly_rate = float(self.hourly_rate_var.get())
            self.hourly_rate = hourly_rate
            logger.info(f"Recalculating finance with rate: {hourly_rate}")
            
            if hasattr(self, 'states') and self.states:
                daily_stats = self.calculate_daily_stats(self.states)
                self.update_finance({
                    'states': self.states,
                    'daily_stats': daily_stats
                })
                
        except ValueError as e:
            logger.error(f"Invalid hourly rate: {e}")
            messagebox.showerror("Chyba", "Neplatná hodinová sazba")
            
    def export_report(self):
        """Exportovat report do HTML"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
            )
            
            if not filename:
                return
                
            logger.info(f"Exporting report to: {filename}")
            
            # Získat data z finance tabu
            finance_content = self.finance_text.get('1.0', 'end')
            
            # Vytvořit HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Activity Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; }}
                    .header {{ background-color: #333; color: white; padding: 20px; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>MacMini Activity Analyzer - Report</h1>
                    <p>Vygenerováno: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                </div>
                <pre>{finance_content}</pre>
            </body>
            </html>
            """
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
                
            logger.info("Report exported successfully")
            messagebox.showinfo("Export", f"Report byl úspěšně exportován do:\n{filename}")
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            messagebox.showerror("Chyba", f"Nepodařilo se exportovat report: {str(e)}")


def main():
    """Hlavní funkce"""
    logger.info("="*70)
    logger.info("APPLICATION STARTUP")
    logger.info("="*70)
    
    try:
        root = tk.Tk()
        app = MacActivityGUI(root)
        logger.info("Starting main event loop")
        root.mainloop()
        
    except Exception as e:
        logger.critical(f"Critical error in main: {e}")
        logger.critical(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()