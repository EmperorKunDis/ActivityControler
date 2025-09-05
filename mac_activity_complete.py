#!/usr/bin/env python3
"""
Mac Activity Analyzer - Kompletní verze používající všechny dostupné informace
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

class MacActivityComplete:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Activity Analyzer - Complete")
        self.root.geometry("1400x900")
        
        # Data
        self.all_events = []
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
        
        # Tab 3: Timeline
        self.timeline_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timeline_frame, text='Timeline')
        self.setup_timeline_tab()
        
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
        self.info_frame = ttk.LabelFrame(self.graph_frame, text="Klikněte na graf pro detaily")
        self.info_frame.pack(fill='x', padx=5, pady=5)
        
        self.info_text = tk.Text(self.info_frame, height=5, wrap='word')
        self.info_text.pack(fill='x', padx=5, pady=5)
        
    def setup_stats_tab(self):
        """Nastavit statistiky tab"""
        self.stats_text = scrolledtext.ScrolledText(self.stats_frame, wrap='word', height=40)
        self.stats_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def setup_timeline_tab(self):
        """Nastavit timeline tab"""
        self.timeline_text = scrolledtext.ScrolledText(self.timeline_frame, wrap='word', height=40, font=('Courier', 10))
        self.timeline_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def process_queue(self):
        """Zpracovat zprávy z fronty"""
        try:
            while True:
                msg = self.queue.get_nowait()
                
                if msg['type'] == 'status':
                    self.status_var.set(msg['text'])
                elif msg['type'] == 'states':
                    self.display_graph(msg['states'])
                    self.display_stats(msg['states'])
                elif msg['type'] == 'timeline':
                    self.display_timeline(msg['events'])
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
        except Exception:
            return ""
            
    def analyze_activity(self):
        """Hlavní analýza aktivity - používá VŠECHNY dostupné informace"""
        try:
            self.queue.put({'type': 'status', 'text': 'Načítám všechna data z pmset logu...'})
            
            # Získat VŠECHNY eventy
            all_events = []
            
            # 1. Display eventy - nejlepší indikátor aktivity uživatele
            self.queue.put({'type': 'status', 'text': 'Analyzuji display eventy...'})
            output = self.run_command('pmset -g log | grep "Display is turned" | tail -500')
            for line in output.strip().split('\n'):
                if not line:
                    continue
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    if 'turned on' in line:
                        all_events.append({
                            'timestamp': timestamp,
                            'type': 'display_on',
                            'category': 'user_activity',
                            'description': 'Uživatel zapnul obrazovku'
                        })
                    else:
                        all_events.append({
                            'timestamp': timestamp,
                            'type': 'display_off',
                            'category': 'user_activity',
                            'description': 'Uživatel vypnul obrazovku'
                        })
                        
            # 2. Sleep eventy - kdy počítač usíná
            self.queue.put({'type': 'status', 'text': 'Analyzuji sleep eventy...'})
            output = self.run_command('pmset -g log | grep "Entering Sleep" | tail -500')
            for line in output.strip().split('\n'):
                if not line:
                    continue
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    # Získat důvod uspání
                    reason = "Unknown"
                    if "Clamshell Sleep" in line:
                        reason = "Zavření víka"
                    elif "Maintenance Sleep" in line:
                        reason = "Automatické uspání"
                    elif "Software Sleep" in line:
                        reason = "Manuální uspání"
                        
                    all_events.append({
                        'timestamp': timestamp,
                        'type': 'sleep_start',
                        'category': 'power',
                        'description': f'Uspání: {reason}'
                    })
                    
            # 3. Wake eventy - probuzení
            self.queue.put({'type': 'status', 'text': 'Analyzuji wake eventy...'})
            
            # DarkWake - probuzení na pozadí
            output = self.run_command('pmset -g log | grep "DarkWake" | tail -500')
            for line in output.strip().split('\n'):
                if not line:
                    continue
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    
                    if "DarkWake to FullWake" in line:
                        all_events.append({
                            'timestamp': timestamp,
                            'type': 'wake_full',
                            'category': 'power',
                            'description': 'Plné probuzení (uživatel)'
                        })
                    else:
                        all_events.append({
                            'timestamp': timestamp,
                            'type': 'wake_dark',
                            'category': 'power',
                            'description': 'Probuzení na pozadí'
                        })
                        
            # 4. Boot/Shutdown z last příkazu
            self.queue.put({'type': 'status', 'text': 'Analyzuji boot/shutdown eventy...'})
            
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
                            all_events.append({
                                'timestamp': timestamp,
                                'type': 'boot',
                                'category': 'system',
                                'description': 'Start systému'
                            })
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
                            all_events.append({
                                'timestamp': timestamp,
                                'type': 'shutdown',
                                'category': 'system',
                                'description': 'Vypnutí systému'
                            })
                        except:
                            pass
                            
            # Seřadit eventy podle času
            all_events.sort(key=lambda x: x['timestamp'])
            
            # Omezit na posledních 10 dní
            ten_days_ago = datetime.now() - timedelta(days=10)
            all_events = [e for e in all_events if e['timestamp'] > ten_days_ago]
            
            # Odeslat timeline
            self.all_events = all_events
            self.queue.put({'type': 'timeline', 'events': all_events})
            
            # Vytvořit stavy z eventů
            self.queue.put({'type': 'status', 'text': 'Vytvářím časové stavy...'})
            states = self.create_states_from_events(all_events)
            
            self.states = states
            self.queue.put({'type': 'states', 'states': states})
            
            self.queue.put({'type': 'status', 'text': f'Analýza dokončena - nalezeno {len(all_events)} eventů'})
            
        except Exception as e:
            self.queue.put({'type': 'error', 'text': f'Chyba při analýze: {str(e)}'})
            
        finally:
            self.root.after(100, lambda: self.refresh_btn.config(state='normal'))
            
    def create_states_from_events(self, events):
        """Vytvořit stavy z eventů s inteligentní logikou"""
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
            
            # Určit další timestamp pro ukončení stavu
            next_timestamp = events[i+1]['timestamp'] if i+1 < len(events) else datetime.now()
            
            # Zpracovat event
            if event_type == 'boot':
                # Systém naběhl
                if i > 0:  # Ukončit předchozí shutdown stav
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': 'shutdown',
                        'color': 'black'
                    })
                system_on = True
                display_on = True  # Po bootu je display zapnutý
                last_activity = timestamp
                current_state_start = timestamp
                
            elif event_type == 'shutdown':
                # Ukončit aktivní stav
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
                
            elif event_type == 'sleep_start':
                # Ukončit aktivní období
                if system_on and not event.get('processed'):
                    state = self._determine_state(display_on, last_activity, timestamp)
                    states.append({
                        'start': current_state_start,
                        'end': timestamp,
                        'state': state,
                        'color': 'green' if state == 'active' else 'red'
                    })
                    current_state_start = timestamp
                    display_on = False
                    
            elif event_type in ['wake_full', 'wake_dark']:
                # Probuzení - ukončit sleep
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
                # Uživatel zapnul obrazovku
                if not display_on and system_on:
                    # Ukončit neaktivní/sleep období
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
                # Uživatel vypnul obrazovku
                if display_on and system_on:
                    # Ukončit aktivní období
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
                    # Vložit aktivní období a začít neaktivní
                    active_end = last_activity + timedelta(seconds=60)
                    if active_end > current_state_start:
                        states.append({
                            'start': current_state_start,
                            'end': active_end,
                            'state': 'active',
                            'color': 'green'
                        })
                        current_state_start = active_end
                    last_activity = None  # Reset pro další aktivitu
                    
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
                # Sloučit
                current['end'] = state['end']
            else:
                merged.append(current)
                current = state
                
        merged.append(current)
        return merged
        
    def display_graph(self, states):
        """Zobrazit graf"""
        self.ax.clear()
        
        if not states:
            self.ax.text(0.5, 0.5, 'Žádná data', ha='center', va='center')
            self.canvas.draw()
            return
            
        # Seskupit stavy podle dnů
        days = {}
        for state in states:
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
        self.ax.set_title('Mac Activity Timeline - Kompletní analýza', fontsize=14, fontweight='bold')
        
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
                        value = (duration/3600) * 250
                        info += f"Hodnota: {value:.2f} Kč"
                        
                    self.info_text.delete('1.0', 'end')
                    self.info_text.insert('1.0', info)
                    break
                    
    def display_stats(self, states):
        """Zobrazit statistiky"""
        self.stats_text.delete('1.0', 'end')
        
        # Denní statistiky
        days = {}
        for state in states:
            day = state['start'].date()
            if day not in days:
                days[day] = {'active': 0, 'inactive': 0, 'sleep': 0, 'shutdown': 0}
                
            duration = (state['end'] - state['start']).total_seconds() / 3600
            state_type = state['state']
            
            if state_type in days[day]:
                days[day][state_type] += duration
                
        # Zobrazit
        text = "📊 DENNÍ STATISTIKY\n"
        text += "="*60 + "\n\n"
        
        total = {'active': 0, 'inactive': 0, 'sleep': 0, 'shutdown': 0}
        
        for day in sorted(days.keys(), reverse=True):
            stats = days[day]
            
            text += f"{day.strftime('%Y-%m-%d (%A)')}\n"
            text += "-"*40 + "\n"
            
            # První a poslední aktivita
            day_states = [s for s in states if s['start'].date() == day]
            if day_states:
                first_active = min(s['start'] for s in day_states if s['state'] == 'active')
                last_active = max(s['end'] for s in day_states if s['state'] == 'active')
                text += f"První aktivita: {first_active.strftime('%H:%M')}\n"
                text += f"Poslední aktivita: {last_active.strftime('%H:%M')}\n"
                
            text += f"✅ Aktivní: {stats['active']:.2f}h\n"
            text += f"⏸️  Neaktivní: {stats['inactive']:.2f}h\n"
            text += f"💤 Spánek: {stats['sleep']:.2f}h\n"
            text += f"⚫ Vypnuto: {stats['shutdown']:.2f}h\n"
            
            total_hours = sum(stats.values())
            if total_hours > 0:
                efficiency = (stats['active'] / total_hours) * 100
                text += f"📈 Efektivita: {efficiency:.1f}%\n"
                
            text += "\n"
            
            for key in total:
                total[key] += stats[key]
                
        # Celkový souhrn
        text += "="*60 + "\n"
        text += "📊 CELKOVÝ SOUHRN\n"
        text += "="*60 + "\n"
        text += f"✅ Celkem aktivní: {total['active']:.2f} hodin\n"
        text += f"⏸️  Celkem neaktivní: {total['inactive']:.2f} hodin\n"
        text += f"💤 Celkem spánek: {total['sleep']:.2f} hodin\n"
        text += f"⚫ Celkem vypnuto: {total['shutdown']:.2f} hodin\n\n"
        
        # Finance
        hourly_rate = 250
        total_money = total['active'] * hourly_rate
        avg_daily = total_money / len(days) if days else 0
        
        text += "💰 FINANČNÍ KALKULACE\n"
        text += "="*60 + "\n"
        text += f"Hodinová sazba: {hourly_rate} Kč/hod\n"
        text += f"Odpracované hodiny: {total['active']:.2f}h\n"
        text += f"Celková částka: {total_money:,.2f} Kč\n"
        text += f"Průměr na den: {avg_daily:,.2f} Kč\n"
        text += f"Projekce měsíc (22 dní): {avg_daily * 22:,.2f} Kč\n"
        
        self.stats_text.insert('1.0', text)
        
    def display_timeline(self, events):
        """Zobrazit timeline eventů"""
        self.timeline_text.delete('1.0', 'end')
        
        text = "📅 TIMELINE VŠECH EVENTŮ\n"
        text += "="*80 + "\n\n"
        
        # Seskupit podle dnů
        days = {}
        for event in events:
            day = event['timestamp'].date()
            if day not in days:
                days[day] = []
            days[day].append(event)
            
        # Zobrazit
        for day in sorted(days.keys(), reverse=True):
            text += f"\n{day.strftime('%Y-%m-%d (%A)')}\n"
            text += "-"*80 + "\n"
            
            for event in sorted(days[day], key=lambda x: x['timestamp']):
                time_str = event['timestamp'].strftime('%H:%M:%S')
                type_str = event['type'].ljust(15)
                desc = event['description']
                
                # Barevné označení
                if event['category'] == 'user_activity':
                    emoji = "👤"
                elif event['category'] == 'power':
                    emoji = "⚡"
                else:
                    emoji = "💻"
                    
                text += f"{time_str} | {emoji} {type_str} | {desc}\n"
                
        self.timeline_text.insert('1.0', text)


def main():
    root = tk.Tk()
    app = MacActivityComplete(root)
    root.mainloop()


if __name__ == "__main__":
    main()