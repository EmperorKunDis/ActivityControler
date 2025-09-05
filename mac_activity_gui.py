#!/usr/bin/env python3
"""
MacMini Activity Analyzer GUI
Interaktivní desktop aplikace pro analýzu aktivity Mac počítače
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

class MacActivityGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MacMini Activity Analyzer 💻")
        self.root.geometry("1400x900")
        
        # Pro Apple Silicon Mac
        try:
            self.root.tk.call('tk', 'scaling', 2.0)
        except:
            pass
        
        # Data storage
        self.events = []
        self.states = []
        self.selected_state = None
        self.hourly_rate = 10000 / 40  # 250 Kč/hodina
        
        # Queue pro thread komunikaci
        self.queue = queue.Queue()
        
        # Setup GUI
        self.setup_gui()
        
        # Auto-start analýzy
        self.root.after(100, self.start_analysis)
    
    def setup_gui(self):
        """Vytvoří GUI layout"""
        
        # Hlavní kontejner
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Konfigurace grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)
        
        # Header panel
        header_frame = ttk.LabelFrame(main_container, text="📊 Kontrolní Panel", padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Tlačítka
        self.analyze_btn = ttk.Button(header_frame, text="🔄 Obnovit Data", command=self.start_analysis)
        self.analyze_btn.grid(row=0, column=0, padx=5)
        
        self.export_btn = ttk.Button(header_frame, text="💾 Exportovat Report", command=self.export_report)
        self.export_btn.grid(row=0, column=1, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(header_frame, mode='indeterminate')
        self.progress.grid(row=0, column=2, padx=20, sticky=(tk.W, tk.E))
        
        # Status label
        self.status_label = ttk.Label(header_frame, text="⏳ Připraveno k analýze")
        self.status_label.grid(row=0, column=3, padx=5)
        
        # Notebook pro taby
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Tab 1: Graf
        self.graph_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text="📈 Graf Aktivity")
        
        # Tab 2: Statistiky
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="📊 Statistiky")
        
        # Tab 3: Finanční přehled
        self.finance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.finance_frame, text="💰 Finanční Přehled")
        
        # Tab 4: Raw Data
        self.raw_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_frame, text="📝 Raw Data")
        
        self.setup_graph_tab()
        self.setup_stats_tab()
        self.setup_finance_tab()
        self.setup_raw_tab()
    
    def setup_graph_tab(self):
        """Nastaví tab s grafem"""
        # Canvas pro matplotlib
        self.figure, self.ax = plt.subplots(figsize=(12, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Info panel pod grafem
        self.info_frame = ttk.LabelFrame(self.graph_frame, text="ℹ️ Detaily vybraného úseku", padding="10")
        self.info_frame.pack(fill=tk.X, pady=10)
        
        self.detail_text = tk.Text(self.info_frame, height=4, width=80)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        
        # Event handler pro klikání
        self.canvas.mpl_connect('button_press_event', self.on_graph_click)
    
    def setup_stats_tab(self):
        """Nastaví tab se statistikami"""
        # Treeview pro statistiky
        columns = ('Den', 'Aktivní', 'Pauzy', 'Spánek', 'Vypnuto', 'Celkem')
        self.stats_tree = ttk.Treeview(self.stats_frame, columns=columns, show='tree headings', height=15)
        
        # Definice sloupců
        self.stats_tree.heading('#0', text='')
        self.stats_tree.column('#0', width=0, stretch=False)
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
            self.stats_tree.column(col, width=120)
        
        # Scrollbary
        vsb = ttk.Scrollbar(self.stats_frame, orient="vertical", command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=vsb.set)
        
        self.stats_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.stats_frame.columnconfigure(0, weight=1)
        self.stats_frame.rowconfigure(0, weight=1)
        
        # Souhrn panel
        self.summary_frame = ttk.LabelFrame(self.stats_frame, text="📊 Celkový Souhrn", padding="10")
        self.summary_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.summary_text = tk.Text(self.summary_frame, height=5, width=80)
        self.summary_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
    
    def setup_finance_tab(self):
        """Nastaví tab s finančním přehledem"""
        # Frame pro nastavení sazby
        rate_frame = ttk.LabelFrame(self.finance_frame, text="⚙️ Nastavení Sazby", padding="10")
        rate_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(rate_frame, text="Hodinová sazba (Kč/hod):").grid(row=0, column=0, padx=5)
        self.rate_var = tk.StringVar(value=str(self.hourly_rate))
        self.rate_entry = ttk.Entry(rate_frame, textvariable=self.rate_var, width=10)
        self.rate_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(rate_frame, text="Přepočítat", command=self.recalculate_finance).grid(row=0, column=2, padx=5)
        
        # Treeview pro finanční přehled
        fin_columns = ('Období', 'Odpracované hodiny', 'Částka (Kč)', 'Efektivita (%)')
        self.finance_tree = ttk.Treeview(self.finance_frame, columns=fin_columns, show='tree headings', height=12)
        
        self.finance_tree.heading('#0', text='')
        self.finance_tree.column('#0', width=0, stretch=False)
        
        for col in fin_columns:
            self.finance_tree.heading(col, text=col)
            self.finance_tree.column(col, width=200)
        
        self.finance_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Celkový souhrn
        self.finance_summary = ttk.LabelFrame(self.finance_frame, text="💰 Finanční Souhrn", padding="10")
        self.finance_summary.pack(fill=tk.X, pady=10)
        
        self.finance_summary_text = tk.Text(self.finance_summary, height=6, width=80)
        self.finance_summary_text.pack(fill=tk.BOTH)
    
    def setup_raw_tab(self):
        """Nastaví tab s raw daty"""
        # ScrolledText pro raw data
        self.raw_text = scrolledtext.ScrolledText(self.raw_frame, wrap=tk.WORD, width=100, height=30)
        self.raw_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def start_analysis(self):
        """Spustí analýzu v samostatném vláknu"""
        self.analyze_btn.config(state='disabled')
        self.progress.start()
        self.status_label.config(text="🔄 Načítám data...")
        
        # Spustit analýzu v threadu
        thread = threading.Thread(target=self.run_analysis_thread)
        thread.daemon = True
        thread.start()
        
        # Zkontrolovat frontu pro výsledky
        self.root.after(100, self.check_queue)
    
    def check_queue(self):
        """Kontroluje frontu pro výsledky z threadu"""
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == 'status':
                    self.status_label.config(text=msg['text'])
                elif msg['type'] == 'complete':
                    self.events = msg['events']
                    self.states = msg['states']
                    self.update_display()
                    self.progress.stop()
                    self.analyze_btn.config(state='normal')
                    self.status_label.config(text="✅ Analýza dokončena")
                elif msg['type'] == 'error':
                    messagebox.showerror("Chyba", msg['text'])
                    self.progress.stop()
                    self.analyze_btn.config(state='normal')
                    self.status_label.config(text="❌ Chyba při analýze")
        except queue.Empty:
            pass
        
        if self.analyze_btn['state'] == 'disabled':
            self.root.after(100, self.check_queue)
    
    def run_analysis_thread(self):
        """Běží v samostatném vláknu a provádí analýzu"""
        try:
            # Získání dat
            self.queue.put({'type': 'status', 'text': '📥 Získávám pmset logy...'})
            pmset_output = self.run_command("pmset -g log | grep -E 'Wake|Sleep|Shutdown|Display' | tail -500")
            
            self.queue.put({'type': 'status', 'text': '📥 Získávám reboot logy...'})
            reboot_output = self.run_command("last reboot | head -20")
            
            # Parsování
            self.queue.put({'type': 'status', 'text': '🔍 Analyzuji data...'})
            events = self.parse_all_logs(pmset_output, reboot_output)
            
            # Filtrování na posledních 10 dní
            ten_days_ago = datetime.now() - timedelta(days=10)
            filtered_events = [e for e in events if e['timestamp'] >= ten_days_ago]
            
            if not filtered_events:
                self.queue.put({'type': 'error', 'text': 'Nenalezena žádná data za posledních 10 dní!'})
                return
            
            # Analýza intervalů
            states = self.analyze_intervals(filtered_events)
            
            self.queue.put({
                'type': 'complete',
                'events': filtered_events,
                'states': states
            })
            
        except Exception as e:
            self.queue.put({'type': 'error', 'text': str(e)})
    
    def run_command(self, command: str) -> str:
        """Spustí shell příkaz"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return ""
    
    def parse_all_logs(self, pmset_log: str, reboot_log: str) -> List[Dict]:
        """Parsuje všechny logy"""
        events = []
        
        # Parse pmset log
        patterns = {
            'wake': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+.*Wake from',
            'sleep': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+.*Sleep',
            'shutdown': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+.*Shutdown',
            'display_sleep': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+.*Display is turned off',
            'display_wake': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+.*Display is turned on',
        }
        
        for line in pmset_log.split('\n'):
            for event_type, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    timestamp_str = match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    events.append({
                        'timestamp': timestamp,
                        'type': event_type,
                        'raw': line
                    })
                    break
        
        # Parse reboot log
        for line in reboot_log.split('\n'):
            if 'reboot' in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        date_str = ' '.join(parts[-4:])
                        year = datetime.now().year
                        date_str_with_year = f"{year} {date_str}"
                        timestamp = datetime.strptime(date_str_with_year, '%Y %a %b %d %H:%M')
                        
                        if timestamp > datetime.now():
                            timestamp = timestamp.replace(year=year-1)
                        
                        events.append({
                            'timestamp': timestamp,
                            'type': 'reboot',
                            'raw': line
                        })
                    except:
                        continue
        
        return sorted(events, key=lambda x: x['timestamp'])
    
    def analyze_intervals(self, events: List[Dict]) -> List[Dict]:
        """Analyzuje intervaly mezi událostmi"""
        states = []
        
        for i in range(len(events)):
            current_event = events[i]
            
            # Určení stavu
            if current_event['type'] in ['wake', 'reboot', 'display_wake']:
                state = 'active'
                color = 'green'
            elif current_event['type'] in ['sleep', 'display_sleep']:
                state = 'sleep'
                color = 'lightgray'
            elif current_event['type'] == 'shutdown':
                state = 'shutdown'
                color = 'black'
            else:
                state = 'unknown'
                color = 'gray'
            
            # Určení konce intervalu
            if i < len(events) - 1:
                end_time = events[i + 1]['timestamp']
            else:
                end_time = datetime.now()
            
            duration = (end_time - current_event['timestamp']).total_seconds()
            
            # Detekce pauz
            if state == 'active' and duration > 60 and i < len(events) - 1:
                next_event = events[i + 1]
                if next_event['type'] not in ['shutdown', 'sleep']:
                    # Rozdělení na aktivní a pauzu
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
                        'raw': f"Pauza delší než 60 sekund (celkem {duration/60:.1f} minut)"
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
    
    def update_display(self):
        """Aktualizuje všechny zobrazení"""
        self.draw_graph()
        self.update_stats()
        self.update_finance()
        self.update_raw_data()
    
    def draw_graph(self):
        """Vykreslí graf aktivity"""
        self.ax.clear()
        
        if not self.states:
            self.ax.text(0.5, 0.5, 'Žádná data k zobrazení', 
                        ha='center', va='center', transform=self.ax.transAxes)
            self.canvas.draw()
            return
        
        # Příprava dat po dnech
        days = {}
        for state in self.states:
            day = state['start'].date()
            if day not in days:
                days[day] = []
            days[day].append(state)
        
        # Vykreslení
        y_pos = 0
        y_labels = []
        
        for day in sorted(days.keys(), reverse=True):
            day_states = days[day]
            y_labels.append(day.strftime('%d.%m.%Y'))
            
            for state in day_states:
                start = mdates.date2num(state['start'])
                end = mdates.date2num(state['end'])
                width = end - start
                
                rect = Rectangle((start, y_pos - 0.4), width, 0.8,
                               facecolor=state['color'],
                               edgecolor='black',
                               linewidth=0.5,
                               picker=True)
                rect.state_data = state  # Uložíme data pro klikání
                self.ax.add_patch(rect)
            
            y_pos += 1
        
        # Nastavení os
        self.ax.set_ylim(-0.5, len(days) - 0.5)
        self.ax.set_yticks(range(len(days)))
        self.ax.set_yticklabels(y_labels)
        
        # Formátování časové osy
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        
        # Legenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', label='Aktivní (<60s)'),
            Patch(facecolor='red', label='Pauza (>60s)'),
            Patch(facecolor='lightgray', label='Spánek'),
            Patch(facecolor='black', label='Vypnuto')
        ]
        self.ax.legend(handles=legend_elements, loc='upper right')
        
        self.ax.set_xlabel('Čas')
        self.ax.set_ylabel('Den')
        self.ax.set_title('Aktivita MacMini - Posledních 10 dní')
        self.ax.grid(True, alpha=0.3)
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def on_graph_click(self, event):
        """Zpracuje kliknutí na graf"""
        if event.inaxes != self.ax:
            return
        
        # Najít který rectangle byl kliknut
        for child in self.ax.get_children():
            if isinstance(child, Rectangle) and hasattr(child, 'state_data'):
                if child.contains(event)[0]:
                    state = child.state_data
                    self.show_state_detail(state)
                    break
    
    def show_state_detail(self, state):
        """Zobrazí detail vybraného stavu"""
        self.detail_text.delete(1.0, tk.END)
        
        detail = f"""📍 DETAIL VYBRANÉHO ÚSEKU
════════════════════════════════════════════
Typ: {state['event_type'].upper()}
Stav: {state['state'].upper()}
Start: {state['start'].strftime('%d.%m.%Y %H:%M:%S')}
Konec: {state['end'].strftime('%d.%m.%Y %H:%M:%S')}
Trvání: {state['duration']/60:.1f} minut ({state['duration']/3600:.2f} hodin)
Hodnota: {(state['duration']/3600) * self.hourly_rate:.2f} Kč

Raw data: {state.get('raw', 'N/A')[:100]}...
"""
        self.detail_text.insert(1.0, detail)
    
    def update_stats(self):
        """Aktualizuje statistiky"""
        # Vyčistit treeview
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        
        # Spočítat statistiky po dnech
        days = {}
        for state in self.states:
            day = state['start'].date()
            if day not in days:
                days[day] = {'active': 0, 'pause': 0, 'sleep': 0, 'shutdown': 0}
            if state['state'] in days[day]:
                days[day][state['state']] += state['duration'] / 3600
        
        # Přidat do treeview
        total = {'active': 0, 'pause': 0, 'sleep': 0, 'shutdown': 0}
        
        for day in sorted(days.keys(), reverse=True):
            stats = days[day]
            total_day = sum(stats.values())
            
            self.stats_tree.insert('', 'end', values=(
                day.strftime('%d.%m.%Y'),
                f"{stats['active']:.2f}h",
                f"{stats['pause']:.2f}h",
                f"{stats['sleep']:.2f}h",
                f"{stats['shutdown']:.2f}h",
                f"{total_day:.2f}h"
            ))
            
            for key in total:
                total[key] += stats[key]
        
        # Celkový souhrn
        self.summary_text.delete(1.0, tk.END)
        summary = f"""📊 CELKOVÝ SOUHRN ZA POSLEDNÍCH 10 DNÍ:
✅ Aktivní čas: {total['active']:.2f} hodin
⏸️  Pauzy (>60s): {total['pause']:.2f} hodin  
💤 Spánek: {total['sleep']:.2f} hodin
⚫ Vypnuto: {total['shutdown']:.2f} hodin
════════════════════════════════════════════
📅 CELKEM: {sum(total.values()):.2f} hodin"""
        self.summary_text.insert(1.0, summary)
    
    def update_finance(self):
        """Aktualizuje finanční přehled"""
        try:
            self.hourly_rate = float(self.rate_var.get())
        except:
            self.hourly_rate = 250
        
        # Vyčistit treeview
        for item in self.finance_tree.get_children():
            self.finance_tree.delete(item)
        
        # Spočítat finance po týdnech
        weeks = {}
        for state in self.states:
            if state['state'] == 'active':
                week = state['start'].isocalendar()[1]
                year = state['start'].year
                week_key = f"{year}-T{week}"
                
                if week_key not in weeks:
                    weeks[week_key] = {'hours': 0, 'total_hours': 0}
                weeks[week_key]['hours'] += state['duration'] / 3600
        
        # Přidat celkové hodiny pro efektivitu
        for state in self.states:
            week = state['start'].isocalendar()[1]
            year = state['start'].year
            week_key = f"{year}-T{week}"
            if week_key in weeks:
                weeks[week_key]['total_hours'] += state['duration'] / 3600
        
        # Přidat do treeview
        total_hours = 0
        total_money = 0
        
        for week in sorted(weeks.keys(), reverse=True):
            data = weeks[week]
            money = data['hours'] * self.hourly_rate
            efficiency = (data['hours'] / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
            
            self.finance_tree.insert('', 'end', values=(
                f"Týden {week}",
                f"{data['hours']:.2f}",
                f"{money:.2f} Kč",
                f"{efficiency:.1f}%"
            ))
            
            total_hours += data['hours']
            total_money += money
        
        # Celkový finanční souhrn
        self.finance_summary_text.delete(1.0, tk.END)
        
        # Výpočet průměrů
        days_count = len(set(state['start'].date() for state in self.states))
        avg_daily = total_money / days_count if days_count > 0 else 0
        projected_monthly = avg_daily * 22  # Pracovní dny v měsíci
        
        finance_summary = f"""💰 FINANČNÍ SOUHRN:
════════════════════════════════════════════
📊 Odpracované hodiny: {total_hours:.2f} h
💵 Hodinová sazba: {self.hourly_rate:.2f} Kč/h
💰 Celková částka: {total_money:,.2f} Kč

📈 Průměr na den: {avg_daily:,.2f} Kč
📅 Projekce na měsíc (22 dní): {projected_monthly:,.2f} Kč
🎯 Efektivita: {(total_hours / (sum(s['duration']/3600 for s in self.states)) * 100):.1f}%"""
        
        self.finance_summary_text.insert(1.0, finance_summary)
    
    def update_raw_data(self):
        """Aktualizuje raw data tab"""
        self.raw_text.delete(1.0, tk.END)
        
        raw_output = "=== RAW DATA LOG ===\n\n"
        
        for event in sorted(self.events, key=lambda x: x['timestamp'], reverse=True):
            raw_output += f"{event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | {event['type']:15} | {event.get('raw', 'N/A')[:100]}\n"
        
        self.raw_text.insert(1.0, raw_output)
    
    def recalculate_finance(self):
        """Přepočítá finanční údaje"""
        self.update_finance()
        messagebox.showinfo("Přepočítáno", "Finanční údaje byly přepočítány s novou sazbou.")
    
    def export_report(self):
        """Exportuje report do HTML"""
        if not self.states:
            messagebox.showwarning("Varování", "Nejsou žádná data k exportu!")
            return
        
        # Generovat HTML report
        html = self.generate_html_report()
        
        # Uložit soubor
        filename = f"mac_activity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        messagebox.showinfo("Export", f"Report byl uložen jako:\n{filename}")
    
    def generate_html_report(self):
        """Generuje HTML report"""
        total_active = sum(s['duration']/3600 for s in self.states if s['state'] == 'active')
        total_money = total_active * self.hourly_rate
        
        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>MacMini Activity Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
        .active {{ background: #90EE90; }}
        .pause {{ background: #FFB6C1; }}
        .sleep {{ background: #D3D3D3; }}
        .shutdown {{ background: #696969; color: white; }}
    </style>
</head>
<body>
    <h1>📊 MacMini Activity Report</h1>
    <p>Vygenerováno: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>💰 Finanční souhrn</h2>
        <p><strong>Odpracované hodiny:</strong> {total_active:.2f} h</p>
        <p><strong>Hodinová sazba:</strong> {self.hourly_rate:.2f} Kč/h</p>
        <p><strong>Celková částka:</strong> {total_money:,.2f} Kč</p>
    </div>
    
    <h2>📈 Detailní přehled aktivit</h2>
    <table>
        <tr>
            <th>Datum/Čas</th>
            <th>Typ</th>
            <th>Stav</th>
            <th>Trvání (min)</th>
            <th>Hodnota (Kč)</th>
        </tr>"""
        
        for state in sorted(self.states, key=lambda x: x['start'], reverse=True)[:100]:
            value = (state['duration']/3600 * self.hourly_rate) if state['state'] == 'active' else 0
            html += f"""
        <tr class="{state['state']}">
            <td>{state['start'].strftime('%d.%m.%Y %H:%M')}</td>
            <td>{state['event_type']}</td>
            <td>{state['state']}</td>
            <td>{state['duration']/60:.1f}</td>
            <td>{value:.2f}</td>
        </tr>"""
        
        html += """
    </table>
</body>
</html>"""
        
        return html

def main():
    """Hlavní funkce"""
    root = tk.Tk()
    app = MacActivityGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()