#!/usr/bin/env python3
"""
Mac Activity Analyzer - Opravená verze s původní logikou
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
from collections import defaultdict
import threading
import queue

class MacActivityAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Activity Analyzer")
        self.root.geometry("1400x900")
        
        # Data
        self.events = []
        self.states = []
        self.queue = queue.Queue()
        
        # GUI
        self.setup_gui()
        
        # Automaticky spustit analýzu
        self.root.after(100, self.start_analysis)
        
    def setup_gui(self):
        """Vytvořit GUI"""
        # Notebook s taby
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
        
        # Tab 3: Raw data
        self.raw_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_frame, text='Raw Data')
        self.setup_raw_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="Připraven")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x', padx=5, pady=2)
        
        # Refresh button
        self.refresh_btn = ttk.Button(self.root, text="🔄 Obnovit analýzu", command=self.start_analysis)
        self.refresh_btn.pack(side='bottom', pady=5)
        
        # Periodické zpracování fronty
        self.process_queue()
        
    def setup_graph_tab(self):
        """Nastavit graf tab"""
        # Matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(14, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Info frame
        self.info_frame = ttk.LabelFrame(self.graph_frame, text="Informace o vybraném období")
        self.info_frame.pack(fill='x', padx=5, pady=5)
        
        self.info_text = tk.Text(self.info_frame, height=4, wrap='word')
        self.info_text.pack(fill='x', padx=5, pady=5)
        
    def setup_stats_tab(self):
        """Nastavit statistiky tab"""
        # Scrolled text pro statistiky
        self.stats_text = scrolledtext.ScrolledText(self.stats_frame, wrap='word', height=40)
        self.stats_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def setup_raw_tab(self):
        """Nastavit raw data tab"""
        self.raw_text = scrolledtext.ScrolledText(self.raw_frame, wrap='word', height=40)
        self.raw_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def process_queue(self):
        """Zpracovat zprávy z fronty"""
        try:
            while True:
                msg = self.queue.get_nowait()
                
                if msg['type'] == 'status':
                    self.status_var.set(msg['text'])
                elif msg['type'] == 'events':
                    self.display_events(msg['events'])
                elif msg['type'] == 'states':
                    self.display_states(msg['states'])
                    self.display_stats(msg['states'])
                elif msg['type'] == 'error':
                    messagebox.showerror("Chyba", msg['text'])
                    
        except queue.Empty:
            pass
            
        self.root.after(100, self.process_queue)
        
    def start_analysis(self):
        """Spustit analýzu v threadu"""
        self.refresh_btn.config(state='disabled')
        thread = threading.Thread(target=self.analyze_activity, daemon=True)
        thread.start()
        
    def run_command(self, cmd):
        """Spustit příkaz a vrátit výstup"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception as e:
            return ""
            
    def analyze_activity(self):
        """Hlavní analýza aktivity"""
        try:
            self.queue.put({'type': 'status', 'text': 'Načítám data...'})
            
            # 1. Získat všechny eventy
            all_events = []
            
            # Display eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji display eventy...'})
            display_events = self.get_display_events()
            all_events.extend(display_events)
            
            # Sleep eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji sleep eventy...'})
            sleep_events = self.get_sleep_events()
            all_events.extend(sleep_events)
            
            # Wake eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji wake eventy...'})
            wake_events = self.get_wake_events()
            all_events.extend(wake_events)
            
            # Boot/shutdown eventy
            self.queue.put({'type': 'status', 'text': 'Analyzuji boot/shutdown eventy...'})
            boot_events = self.get_boot_shutdown_events()
            all_events.extend(boot_events)
            
            # Seřadit eventy podle času
            all_events.sort(key=lambda x: x['timestamp'])
            
            # Uložit eventy
            self.events = all_events
            self.queue.put({'type': 'events', 'events': all_events})
            
            # 2. Vytvořit stavy - používám původní logiku
            self.queue.put({'type': 'status', 'text': 'Vytvářím časové stavy...'})
            states = self.analyze_events(all_events)
            
            self.states = states
            self.queue.put({'type': 'states', 'states': states})
            
            self.queue.put({'type': 'status', 'text': 'Analýza dokončena'})
            
        except Exception as e:
            self.queue.put({'type': 'error', 'text': f'Chyba při analýze: {str(e)}'})
            
        finally:
            self.root.after(100, lambda: self.refresh_btn.config(state='normal'))
            
    def get_display_events(self):
        """Získat display on/off eventy"""
        events = []
        output = self.run_command('pmset -g log | grep "Display is turned" | tail -200')
        
        for line in output.strip().split('\n'):
            if not line:
                continue
                
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                
                if 'turned on' in line:
                    events.append({
                        'timestamp': timestamp,
                        'type': 'display_on',
                        'raw': line.strip()
                    })
                else:
                    events.append({
                        'timestamp': timestamp,
                        'type': 'display_off',
                        'raw': line.strip()
                    })
                    
        return events
        
    def get_sleep_events(self):
        """Získat sleep eventy"""
        events = []
        output = self.run_command('pmset -g log | grep "Entering Sleep" | tail -200')
        
        for line in output.strip().split('\n'):
            if not line:
                continue
                
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                events.append({
                    'timestamp': timestamp,
                    'type': 'sleep',
                    'raw': line.strip()
                })
                
        return events
        
    def get_wake_events(self):
        """Získat wake eventy"""
        events = []
        output = self.run_command('pmset -g log | grep -E "DarkWake|Wake from|kernel.*wake" | tail -200')
        
        for line in output.strip().split('\n'):
            if not line:
                continue
                
            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                
                if 'DarkWake' in line:
                    events.append({
                        'timestamp': timestamp,
                        'type': 'darkwake',
                        'raw': line.strip()
                    })
                else:
                    events.append({
                        'timestamp': timestamp,
                        'type': 'wake',
                        'raw': line.strip()
                    })
                    
        return events
        
    def get_boot_shutdown_events(self):
        """Získat boot a shutdown eventy"""
        events = []
        
        # Boot eventy
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
                            
                        events.append({
                            'timestamp': timestamp,
                            'type': 'boot',
                            'raw': line.strip()
                        })
                    except:
                        pass
                        
        # Shutdown eventy
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
                            
                        events.append({
                            'timestamp': timestamp,
                            'type': 'shutdown',  
                            'raw': line.strip()
                        })
                    except:
                        pass
                        
        return events
        
    def analyze_events(self, events):
        """Analyzovat eventy a vytvořit stavy - původní logika"""
        states = []
        
        if not events:
            return states
            
        # Omezit na posledních 10 dní
        ten_days_ago = datetime.now() - timedelta(days=10)
        events = [e for e in events if e['timestamp'] > ten_days_ago]
        
        # Seřadit podle času
        events.sort(key=lambda x: x['timestamp'])
        
        for i, current_event in enumerate(events):
            # Najít další event nebo použít současný čas
            if i < len(events) - 1:
                end_time = events[i + 1]['timestamp']
            else:
                end_time = datetime.now()
                
            duration = (end_time - current_event['timestamp']).total_seconds()
            
            # Určit stav podle typu eventu
            event_type = current_event['type']
            
            if event_type in ['boot', 'wake', 'darkwake', 'display_on']:
                state = 'active'
                color = 'green'
            elif event_type in ['sleep']:
                state = 'sleep'
                color = 'lightgray'
            elif event_type in ['shutdown']:
                state = 'shutdown'
                color = 'black'
            elif event_type in ['display_off']:
                state = 'pause'
                color = 'red'
            else:
                state = 'active'
                color = 'green'
                
            # Kontrola 60 sekund pro aktivní stavy
            if state == 'active' and duration > 60:
                # Pokud je mezi eventy více než 60 sekund, rozdělit na aktivní a pauzu
                states.append({
                    'start': current_event['timestamp'],
                    'end': current_event['timestamp'] + timedelta(seconds=60),
                    'state': 'active',
                    'color': 'green',
                    'duration': 60,
                    'event_type': current_event['type'],
                    'raw': current_event.get('raw', '')
                })
                states.append({
                    'start': current_event['timestamp'] + timedelta(seconds=60),
                    'end': end_time,
                    'state': 'pause',
                    'color': 'red',
                    'duration': duration - 60,
                    'event_type': 'pause',
                    'raw': f"Pauza delší než 60 sekund"
                })
                continue
                
            states.append({
                'start': current_event['timestamp'],
                'end': end_time,
                'state': state,
                'color': color,
                'duration': duration,
                'event_type': current_event['type'],
                'raw': current_event.get('raw', '')
            })
            
        return states
        
    def display_events(self, events):
        """Zobrazit eventy v raw data"""
        self.raw_text.delete('1.0', 'end')
        self.raw_text.insert('end', f"Celkem {len(events)} eventů\n")
        self.raw_text.insert('end', "="*60 + "\n\n")
        
        for event in reversed(events[-100:]):
            time_str = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            self.raw_text.insert('end', f"{time_str} | {event['type']:15} | {event.get('raw', '')[:80]}\n")
            
    def display_states(self, states):
        """Zobrazit stavy v grafu"""
        self.ax.clear()
        
        if not states:
            self.ax.text(0.5, 0.5, 'Žádná data', ha='center', va='center')
            self.canvas.draw()
            return
            
        # Připravit data po dnech
        days = {}
        for state in states:
            day = state['start'].date()
            if day not in days:
                days[day] = []
            days[day].append(state)
            
        # Vykreslit graf
        y_pos = 0
        y_labels = []
        
        for day in sorted(days.keys(), reverse=True)[:10]:  # Max 10 dnů
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
        
        # Mřížka a popisky
        self.ax.grid(True, axis='x', alpha=0.3)
        self.ax.set_xlabel('Čas')
        self.ax.set_title('Časová osa aktivity počítače', fontsize=14, fontweight='bold')
        
        # Legenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', edgecolor='black', label='Aktivní (<60s)'),
            Patch(facecolor='red', edgecolor='black', label='Neaktivní (>60s)'),
            Patch(facecolor='lightgray', edgecolor='black', label='Spánek'),
            Patch(facecolor='black', edgecolor='black', label='Vypnuto')
        ]
        self.ax.legend(handles=legend_elements, loc='upper right')
        
        # Event handler pro klikání
        self.canvas.mpl_connect('button_press_event', self.on_click)
        
        self.fig.tight_layout()
        self.canvas.draw()
        
    def on_click(self, event):
        """Handler pro kliknutí na graf"""
        if event.inaxes != self.ax:
            return
            
        # Najít kliknutý rectangle
        for child in self.ax.get_children():
            if isinstance(child, Rectangle) and hasattr(child, 'state_data'):
                if child.contains(event)[0]:
                    state = child.state_data
                    self.show_state_info(state)
                    break
                    
    def show_state_info(self, state):
        """Zobrazit informace o stavu"""
        self.info_text.delete('1.0', 'end')
        
        info = f"Stav: {state['state'].upper()}\n"
        info += f"Od: {state['start'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        info += f"Do: {state['end'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        info += f"Trvání: {state['duration']/60:.1f} minut"
        
        if state['state'] == 'active':
            hours = state['duration'] / 3600
            value = hours * 250  # Default 250 Kč/hod
            info += f"\nHodnota: {value:.2f} Kč"
            
        self.info_text.insert('1.0', info)
        
    def display_stats(self, states):
        """Zobrazit statistiky"""
        self.stats_text.delete('1.0', 'end')
        
        # Spočítat statistiky po dnech
        days = {}
        for state in states:
            day = state['start'].date()
            if day not in days:
                days[day] = {'active': 0, 'pause': 0, 'sleep': 0, 'shutdown': 0}
            if state['state'] in days[day]:
                days[day][state['state']] += state['duration'] / 3600
                
        # Celkové součty
        total = {'active': 0, 'pause': 0, 'sleep': 0, 'shutdown': 0}
        
        text = "DENNÍ STATISTIKY\n"
        text += "="*60 + "\n\n"
        
        for day in sorted(days.keys(), reverse=True)[:10]:
            stats = days[day]
            total_day = sum(stats.values())
            
            text += f"{day.strftime('%Y-%m-%d (%A)')}\n"
            text += "-"*40 + "\n"
            text += f"✅ Aktivní: {stats['active']:.2f}h\n"
            text += f"⏸️  Pauzy (>60s): {stats['pause']:.2f}h\n"
            text += f"💤 Spánek: {stats['sleep']:.2f}h\n"
            text += f"⚫ Vypnuto: {stats['shutdown']:.2f}h\n"
            text += f"📊 Celkem: {total_day:.2f}h\n\n"
            
            for key in total:
                total[key] += stats[key]
                
        # Celkový souhrn
        text += "="*60 + "\n"
        text += "CELKOVÝ SOUHRN\n"
        text += "="*60 + "\n"
        text += f"✅ Celkem aktivní: {total['active']:.2f} hodin\n"
        text += f"⏸️  Celkem pauzy: {total['pause']:.2f} hodin\n"
        text += f"💤 Celkem spánek: {total['sleep']:.2f} hodin\n"
        text += f"⚫ Celkem vypnuto: {total['shutdown']:.2f} hodin\n\n"
        
        # Finance
        hourly_rate = 250
        total_money = total['active'] * hourly_rate
        
        text += "💰 FINANČNÍ KALKULACE\n"
        text += "="*60 + "\n"
        text += f"Hodinová sazba: {hourly_rate} Kč/hod\n"
        text += f"Odpracované hodiny: {total['active']:.2f}h\n"
        text += f"Celková částka: {total_money:,.2f} Kč\n"
        
        # Průměry
        num_days = len(days)
        if num_days > 0:
            avg_daily = total_money / num_days
            text += f"\nPrůměr na den: {avg_daily:,.2f} Kč\n"
            text += f"Projekce měsíc (22 dní): {avg_daily * 22:,.2f} Kč\n"
            
        self.stats_text.insert('1.0', text)


def main():
    root = tk.Tk()
    app = MacActivityAnalyzer(root)
    root.mainloop()


if __name__ == "__main__":
    main()