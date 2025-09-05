#!/usr/bin/env python3
"""
Mac Activity Analyzer - Advanced Version
Kombinuje automatickou analýzu s pokročilými statistikami a vizualizacemi
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess
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

class MacActivityAdvanced:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Activity Analyzer - Advanced")
        self.root.geometry("1400x900")
        
        # Data
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
        self.queue = queue.Queue()
        
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
        self.hourly_rate_var = tk.StringVar(value="250")
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
                msg = self.queue.get_nowait()
                
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
        thread = threading.Thread(target=self.analyze_activity, daemon=True)
        thread.start()
        
    def run_command(self, cmd):
        """Spustit příkaz a vrátit výstup"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception:
            return ""
            
    def analyze_activity(self):
        """Hlavní analýza aktivity"""
        try:
            self.queue.put({'type': 'status', 'text': 'Načítám data z pmset logu...'})
            
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
            
            # 1. Display eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji display eventy...'})
            self.parse_display_events()
            
            # 2. Sleep/Wake eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji sleep/wake eventy...'})
            self.parse_sleep_wake_events()
            
            # 3. Boot/Shutdown eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji boot/shutdown eventy...'})
            self.parse_boot_shutdown_events()
            
            # 4. Power assertions (aplikace)
            self.queue.put({'type': 'status', 'text': 'Analyzuji aktivitu aplikací...'})
            self.parse_assertions()
            
            # Seřadit všechny eventy
            self.all_events.sort(key=lambda x: x['timestamp'])
            
            # Omezit na posledních 10 dní
            ten_days_ago = datetime.now() - timedelta(days=10)
            self.all_events = [e for e in self.all_events if e['timestamp'] > ten_days_ago]
            
            # Vytvořit stavy
            self.queue.put({'type': 'status', 'text': 'Vytvářím časové stavy...'})
            self.states = self.create_states_from_events(self.all_events)
            
            self.queue.put({'type': 'complete'})
            self.queue.put({'type': 'status', 'text': f'Analýza dokončena - {len(self.all_events)} eventů'})
            
        except Exception as e:
            self.queue.put({'type': 'error', 'text': f'Chyba při analýze: {str(e)}'})
            
    def parse_display_events(self):
        """Parse display events"""
        output = self.run_command('pmset -g log | grep "Display is turned" | tail -500')
        for line in output.strip().split('\n'):
            if not line:
                continue
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                if 'turned on' in line:
                    event = {
                        'timestamp': timestamp,
                        'type': 'display_on',
                        'category': 'display',
                        'description': 'Display zapnut'
                    }
                else:
                    event = {
                        'timestamp': timestamp,
                        'type': 'display_off',
                        'category': 'display',
                        'description': 'Display vypnut'
                    }
                self.all_events.append(event)
                self.parsed_data['display_events'].append(event)
                
    def parse_sleep_wake_events(self):
        """Parse sleep and wake events"""
        # Sleep eventy
        output = self.run_command('pmset -g log | grep "Entering Sleep" | tail -500')
        for line in output.strip().split('\n'):
            if not line:
                continue
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                reason = "Unknown"
                if "Clamshell Sleep" in line:
                    reason = "Zavření víka"
                elif "Maintenance Sleep" in line:
                    reason = "Automatické uspání"
                elif "Software Sleep" in line:
                    reason = "Manuální uspání"
                    
                event = {
                    'timestamp': timestamp,
                    'type': 'sleep',
                    'category': 'power',
                    'description': f'Uspání: {reason}',
                    'details': line
                }
                self.all_events.append(event)
                self.parsed_data['sleep_events'].append(event)
                
        # Wake eventy
        output = self.run_command('pmset -g log | grep -E "DarkWake|Wake from" | tail -500')
        for line in output.strip().split('\n'):
            if not line:
                continue
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                
                if "DarkWake to FullWake" in line:
                    wake_type = 'wake_full'
                    desc = 'Plné probuzení'
                elif "DarkWake" in line:
                    wake_type = 'wake_dark'
                    desc = 'Probuzení na pozadí'
                else:
                    wake_type = 'wake'
                    desc = 'Probuzení'
                    
                event = {
                    'timestamp': timestamp,
                    'type': wake_type,
                    'category': 'power',
                    'description': desc,
                    'details': line
                }
                self.all_events.append(event)
                self.parsed_data['wake_events'].append(event)
                
    def parse_boot_shutdown_events(self):
        """Parse boot and shutdown events"""
        # Reboot
        output = self.run_command('last reboot | head -50')
        for line in output.split('\n'):
            if 'reboot' in line and 'time' in line:
                match = re.search(r'(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})', line)
                if match:
                    try:
                        date_str = match.group(1)
                        timestamp = datetime.strptime(date_str + f' {datetime.now().year}', '%a %b %d %H:%M %Y')
                        if timestamp > datetime.now():
                            timestamp = timestamp.replace(year=datetime.now().year - 1)
                            
                        event = {
                            'timestamp': timestamp,
                            'type': 'boot',
                            'category': 'system',
                            'description': 'Start systému'
                        }
                        self.all_events.append(event)
                        self.parsed_data['reboots'].append(event)
                    except:
                        pass
                        
        # Shutdown
        output = self.run_command('last shutdown | head -50')
        for line in output.split('\n'):
            if 'shutdown' in line and 'time' in line:
                match = re.search(r'(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})', line)
                if match:
                    try:
                        date_str = match.group(1)
                        timestamp = datetime.strptime(date_str + f' {datetime.now().year}', '%a %b %d %H:%M %Y')
                        if timestamp > datetime.now():
                            timestamp = timestamp.replace(year=datetime.now().year - 1)
                            
                        event = {
                            'timestamp': timestamp,
                            'type': 'shutdown',
                            'category': 'system',
                            'description': 'Vypnutí systému'
                        }
                        self.all_events.append(event)
                        self.parsed_data['shutdowns'].append(event)
                    except:
                        pass
                        
    def parse_assertions(self):
        """Parse power assertions (app activity)"""
        output = self.run_command('pmset -g log | grep "Assertions" | tail -1000')
        
        assertion_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*PID (\d+)\(([^)]+)\)\s+(\w+)\s+(.+)'
        
        for line in output.strip().split('\n'):
            if not line:
                continue
                
            match = re.search(assertion_pattern, line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                pid = match.group(2)
                app = match.group(3)
                action = match.group(4)
                details = match.group(5)
                
                assertion = {
                    'timestamp': timestamp,
                    'type': 'assertion',
                    'category': 'app',
                    'pid': pid,
                    'app': app,
                    'action': action,
                    'description': f'{app}: {action}',
                    'details': details
                }
                
                self.all_events.append(assertion)
                self.parsed_data['assertions'].append(assertion)
                self.parsed_data['app_activity'][app].append(assertion)
                
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
                
            # Kontrola 60 sekund neaktivity
            if display_on and last_activity and system_on:
                time_since_activity = (timestamp - last_activity).total_seconds()
                if time_since_activity > 60:
                    active_end = last_activity + timedelta(seconds=60)
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
        if last_activity and (current_time - last_activity).total_seconds() > 60:
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
        self.display_graph()
        self.generate_overview()
        self.analyze_applications()
        self.analyze_sleep_wake()
        self.generate_statistics()
        self.display_timeline()
        self.update_finance()
        
    def display_graph(self):
        """Zobrazit graf aktivity"""
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
        
        for day in sorted(days.keys(), reverse=True)[:10]:
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
                        value = (duration/3600) * float(self.hourly_rate_var.get())
                        info += f"Hodnota: {value:.2f} Kč"
                        
                    self.info_text.delete('1.0', 'end')
                    self.info_text.insert('1.0', info)
                    break
                    
    def generate_overview(self):
        """Generate overview analysis"""
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
        
    def analyze_applications(self):
        """Analyze application activity"""
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
                event_types[event['action']] += 1
                
            apps_analysis += "  Typy událostí:\n"
            for event_type, count in event_types.most_common(3):
                apps_analysis += f"    • {event_type}: {count}\n"
                
            apps_analysis += "\n"
            
        self.apps_text.insert(tk.END, apps_analysis)
        
    def analyze_sleep_wake(self):
        """Analyze sleep/wake patterns"""
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
        
    def generate_statistics(self):
        """Generate detailed statistics"""
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
        top_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        stats += "🕒 NEJAKTIVNĚJŠÍ HODINY:\n"
        for hour, count in top_hours:
            stats += f"  • {hour:02d}:00 - {count} událostí\n"
            
        stats += "\n📊 CELKOVÉ METRIKY:\n"
        
        total_active_hours = sum(1 for state in self.states if state['state'] == 'active')
        total_active_time = sum((state['end'] - state['start']).total_seconds() / 3600 
                               for state in self.states if state['state'] == 'active')
        
        if self.states:
            efficiency = (total_active_time / (24 * len(set(s['start'].date() for s in self.states)))) * 100
            stats += f"  • Celková efektivita: {efficiency:.1f}%\n"
            stats += f"  • Průměrná aktivní doba/den: {total_active_time / len(set(s['start'].date() for s in self.states)):.2f} hodin\n"
            
        self.stats_text.insert(tk.END, stats)
        
    def display_timeline(self):
        """Display timeline visualization"""
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
        
    def update_finance(self):
        """Update finance calculations"""
        self.finance_text.delete(1.0, tk.END)
        
        try:
            hourly_rate = float(self.hourly_rate_var.get())
        except:
            hourly_rate = 250
            
        finance = "=== FINANČNÍ ANALÝZA ===\n\n"
        
        # Calculate active hours per day
        daily_active = defaultdict(float)
        for state in self.states:
            if state['state'] == 'active':
                day = state['start'].date()
                duration = (state['end'] - state['start']).total_seconds() / 3600
                daily_active[day] += duration
                
        finance += f"💰 NASTAVENÍ:\n"
        finance += f"  • Hodinová sazba: {hourly_rate} Kč/hod\n\n"
        
        finance += "📅 DENNÍ PŘEHLED:\n"
        total_hours = 0
        total_money = 0
        
        for day in sorted(daily_active.keys(), reverse=True):
            hours = daily_active[day]
            money = hours * hourly_rate
            
            finance += f"  {day.strftime('%Y-%m-%d (%A)')}: {hours:.2f}h = {money:,.2f} Kč\n"
            
            total_hours += hours
            total_money += money
            
        finance += f"\n📊 CELKOVÝ SOUHRN:\n"
        finance += f"  • Celkem odpracováno: {total_hours:.2f} hodin\n"
        finance += f"  • Celková částka: {total_money:,.2f} Kč\n"
        
        if daily_active:
            avg_daily = total_money / len(daily_active)
            finance += f"\n📈 PROJEKCE:\n"
            finance += f"  • Průměr na den: {avg_daily:,.2f} Kč\n"
            finance += f"  • Projekce týden (5 dní): {avg_daily * 5:,.2f} Kč\n"
            finance += f"  • Projekce měsíc (22 dní): {avg_daily * 22:,.2f} Kč\n"
            
        self.finance_text.insert(tk.END, finance)
        
    def export_data(self):
        """Export data to file"""
        filename = filedialog.asksaveasfilename(
            title="Uložit report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    # Export as JSON
                    export_data = {
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
                else:
                    # Export as text
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("MAC ACTIVITY REPORT\n")
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
                        
                messagebox.showinfo("Export", f"Data byla exportována do:\n{filename}")
                
            except Exception as e:
                messagebox.showerror("Chyba", f"Nepodařilo se exportovat data:\n{str(e)}")
                
    def load_from_file(self):
        """Load data from file"""
        filename = filedialog.askopenfilename(
            title="Načíst log soubor",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Parse the content
                # This would need to be implemented based on the file format
                messagebox.showinfo("Info", "Funkce načítání souborů bude implementována")
                
            except Exception as e:
                messagebox.showerror("Chyba", f"Nepodařilo se načíst soubor:\n{str(e)}")


def main():
    root = tk.Tk()
    app = MacActivityAdvanced(root)
    root.mainloop()


if __name__ == "__main__":
    main()