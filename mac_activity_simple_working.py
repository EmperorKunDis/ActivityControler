#!/usr/bin/env python3
"""
Mac Activity Analyzer - KOMPLETNÍ A OPRAVENÁ VERZE
Analyzuje aktivitu Mac počítače, s konfigurovatelnými aplikacemi a přesnějším měřením.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import subprocess
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
from collections import defaultdict
import json
import os

# --- Konfigurační manažer ---
class ConfigManager:
    """Spravuje načítání a ukládání nastavení z JSON souboru."""
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.default_config = {
            "hourly_rate": 250,
            "monitored_apps": [
                "Terminal", "Messenger", "Steam", "Discord", "Brave Browser",
                "Safari", "Code", "VSCode", "WhatsApp", "Slack", "iTerm2"
            ],
            "session_timeout_minutes": 30
        }
        self.config = self.load_config()

    def load_config(self):
        """Načte konfiguraci ze souboru, nebo vytvoří výchozí."""
        if not os.path.exists(self.filename):
            self.save_config(self.default_config)
            return self.default_config
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            self.save_config(self.default_config)
            return self.default_config

    def save_config(self, data):
        """Uloží aktuální konfiguraci do souboru."""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self.config = data

# --- Hlavní třída aplikace ---
class MacActivityAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Mac Activity Analyzer v2.1 - Opraveno")
        self.root.geometry("1300x850")

        self.config_manager = ConfigManager()
        
        # Data
        self.power_events = []
        self.app_events = []
        self.states = []
        self.app_usage = defaultdict(lambda: {'sessions': [], 'duration': 0})
        
        # GUI
        self.setup_ui()
        
        # Automatické spuštění analýzy
        self.root.after(100, self.analyze_activity)
        
    def setup_ui(self):
        """Vytvoření GUI prvků."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        tab_names = ["📊 Graf aktivity", "📱 Aplikace", "😴 Spánek", "📈 Statistiky", "🕒 Timeline", "💰 Finance", "⚙️ Nastavení"]
        self.tabs = {}
        for name in tab_names:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=name)
            self.tabs[name] = frame

        self.status_var = tk.StringVar(value="Připraven k analýze")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w')
        status_bar.pack(fill='x', side='bottom', padx=5, pady=2)
        
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="🔄 Obnovit analýzu", command=self.analyze_activity).pack(side='left', padx=2)
        ttk.Button(button_frame, text="💾 Exportovat data", command=self.export_data).pack(side='left', padx=2)
    
    def analyze_activity(self):
        """Hlavní metoda pro spuštění celé analýzy."""
        self.status_var.set("Zahajuji analýzu aktivity za posledních 10 dní...")
        self.root.update_idletasks()

        self.get_power_events()
        self.get_app_events()
        self.analyze_app_usage()
        self.calculate_states()
        
        self.status_var.set("Aktualizuji uživatelské rozhraní...")
        self.root.update_idletasks()
        
        self.update_graph_tab()
        self.update_apps_tab()
        self.update_sleep_tab()
        self.update_stats_tab()
        self.update_timeline_tab()
        self.update_finance_tab()
        self.setup_settings_tab()
        
        self.status_var.set(f"Analýza dokončena. Zpracováno {len(self.app_events)} aplikačních a {len(self.power_events)} power událostí.")

    def get_power_events(self):
        """Získá události spánku/probuzení z `pmset`."""
        self.status_var.set("Získávám data o spánku a probuzení...")
        self.root.update_idletasks()
        try:
            cmd = "pmset -g log | grep -E '(Sleep|Wake|Display)'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            self.power_events = []
            ten_days_ago = datetime.now() - timedelta(days=10)
            
            for line in result.stdout.split('\n'):
                if not line.strip(): continue
                match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    if timestamp >= ten_days_ago:
                        event_type = 'unknown'
                        if 'Sleep' in line: event_type = 'sleep'
                        elif 'Wake' in line: event_type = 'wake'
                        elif 'Display is turned on' in line: event_type = 'display_on'
                        elif 'Display is turned off' in line: event_type = 'display_off'
                        self.power_events.append({'time': timestamp, 'type': event_type, 'description': line.strip()})
            
            self.power_events.sort(key=lambda x: x['time'])
        except Exception as e:
            messagebox.showerror("Chyba `pmset`", f"Nepodařilo se získat data o napájení: {e}")

    def get_app_events(self):
        """Získá události aplikací z `log show` (OPRAVENÁ, ROBUSTNĚJŠÍ VERZE)."""
        self.status_var.set("Získávám data o spuštěných aplikacích (může trvat)...")
        self.root.update_idletasks()
        try:
            monitored_apps = self.config_manager.config.get("monitored_apps", [])
            if not monitored_apps:
                self.app_events = []
                print("Žádné aplikace ke sledování v konfiguraci.")
                return

            pattern = "|".join(re.escape(app) for app in monitored_apps)
            cmd = f"""log show --last 10d --predicate 'eventMessage contains "launched" OR eventMessage contains "terminated" OR processImagePath contains ".app"' --style syslog | grep -iE '({pattern})'"""
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode > 1:
                raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)

            self.app_events = []
            app_name_map = {app.lower(): app for app in monitored_apps}

            lines_to_process = result.stdout.split('\n')
            if len(lines_to_process) > 20000:
                 print(f"Varování: Nalezeno velké množství logů ({len(lines_to_process)} řádků), zpracování může být pomalejší.")

            for line in lines_to_process:
                if not line.strip(): continue
                
                match_time = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not match_time: continue
                
                timestamp = datetime.strptime(match_time.group(1), '%Y-%m-%d %H:%M:%S')

                found_app = None
                for app_lower, app_original in app_name_map.items():
                    if re.search(r'\b' + re.escape(app_lower) + r'\b', line.lower()):
                        found_app = app_original
                        break
                
                if found_app:
                    self.app_events.append({'time': timestamp, 'app': found_app, 'type': 'active'})
            
            self.app_events.sort(key=lambda x: x['time'])
            print(f"Nalezeno {len(self.app_events)} relevantních aplikačních událostí.")

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            messagebox.showerror("Chyba `log show`", f"Nepodařilo se získat data o aplikacích: {e}")
        except Exception as e:
            messagebox.showerror("Neočekávaná chyba", f"Došlo k chybě při zpracování aplikačních logů: {e}")

    def analyze_app_usage(self):
        """Analyzuje dobu používání aplikací na základě session."""
        self.app_usage = defaultdict(lambda: {'sessions': [], 'duration': 0})
        if not self.app_events: return

        events_by_app = defaultdict(list)
        for event in self.app_events:
            events_by_app[event['app']].append(event['time'])

        session_timeout = timedelta(minutes=self.config_manager.config.get("session_timeout_minutes", 30))

        for app, timestamps in events_by_app.items():
            if not timestamps: continue
            
            session_start = timestamps[0]
            last_event_time = timestamps[0]
            
            for i in range(1, len(timestamps)):
                current_event_time = timestamps[i]
                if (current_event_time - last_event_time) > session_timeout:
                    session_end = last_event_time + timedelta(minutes=5)
                    duration = (session_end - session_start).total_seconds()
                    self.app_usage[app]['sessions'].append({'start': session_start, 'end': session_end})
                    self.app_usage[app]['duration'] += duration
                    session_start = current_event_time
                last_event_time = current_event_time

            session_end = last_event_time + timedelta(minutes=5)
            duration = (session_end - session_start).total_seconds()
            self.app_usage[app]['sessions'].append({'start': session_start, 'end': session_end})
            self.app_usage[app]['duration'] += duration

    def calculate_states(self):
        """Vypočítá stavy (aktivní, pauza, spánek) na základě událostí."""
        self.states = []
        all_events = self.power_events[:]
        for app_data in self.app_usage.values():
            for session in app_data['sessions']:
                all_events.append({'time': session['start'], 'type': 'active_start'})
        
        all_events.sort(key=lambda x: x['time'])
        
        if not all_events: return

        current_time = datetime.now() - timedelta(days=10)
        current_state = 'unknown'

        for event in all_events:
            event_time = event['time']
            if event_time < current_time: continue

            duration = (event_time - current_time).total_seconds()
            if duration > 1:
                # Pro stav mezi událostmi určíme, zda byl aktivní
                is_active_in_between = False
                for app_data in self.app_usage.values():
                    for s in app_data['sessions']:
                        if max(current_time, s['start']) < min(event_time, s['end']):
                            is_active_in_between = True
                            break
                    if is_active_in_between: break
                
                state_type = 'active' if is_active_in_between else current_state
                self.states.append({'start': current_time, 'end': event_time, 'type': state_type, 'duration': duration})

            if event['type'] in ['wake', 'display_on', 'active_start']:
                current_state = 'active'
            elif event['type'] in ['sleep', 'display_off']:
                current_state = 'sleep'
            
            current_time = event_time

        if current_time < datetime.now():
            self.states.append({'start': current_time, 'end': datetime.now(), 'type': current_state, 'duration': (datetime.now() - current_time).total_seconds()})

    def clear_tab(self, tab_name):
        frame = self.tabs[tab_name]
        for widget in frame.winfo_children():
            widget.destroy()

    def update_graph_tab(self):
        self.clear_tab("📊 Graf aktivity")
        frame = self.tabs["📊 Graf aktivity"]
        if not self.states:
             ttk.Label(frame, text="Nebylo nalezeno dostatek dat pro vykreslení grafu.").pack(pady=50)
             return

        fig, ax = plt.subplots(figsize=(12, 8))
        colors = {'active': '#2ecc71', 'sleep': '#95a5a6', 'unknown': '#ecf0f1'}
        ten_days_ago = (datetime.now() - timedelta(days=9)).replace(hour=0, minute=0, second=0, microsecond=0)

        for day_offset in range(10):
            current_date = ten_days_ago + timedelta(days=day_offset)
            for hour in range(24):
                for quarter in range(4):
                    start_time = current_date.replace(hour=hour, minute=quarter*15)
                    end_time = start_time + timedelta(minutes=15)
                    state_color = colors['unknown']
                    for state in self.states:
                        if max(state['start'], start_time) < min(state['end'], end_time):
                            state_color = colors.get(state['type'], colors['unknown'])
                            break
                    rect = Rectangle((day_offset, hour + quarter/4), 0.95, 0.23, facecolor=state_color, edgecolor='none')
                    ax.add_patch(rect)
        
        ax.set_xlim(-0.5, 9.5)
        ax.set_ylim(0, 24)
        ax.set_xticks(range(10))
        ax.set_xticklabels([(ten_days_ago + timedelta(days=i)).strftime('%d.%m\n%a') for i in range(10)])
        ax.set_yticks(range(0, 25, 2))
        ax.set_yticklabels([f'{h:02d}:00' for h in range(0, 25, 2)])
        ax.set_ylabel('Hodina')
        ax.set_title('Heatmapa aktivity za posledních 10 dní', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=c, label=l.capitalize()) for l, c in colors.items()]
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1))

        plt.tight_layout(rect=[0, 0, 0.9, 1])
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        plt.close(fig)

    def update_apps_tab(self):
        self.clear_tab("📱 Aplikace")
        frame = self.tabs["📱 Aplikace"]
        if not self.app_usage:
            ttk.Label(frame, text="Nebylo nalezeno dostatek dat o použití aplikací.").pack(pady=50)
            return

        tree = ttk.Treeview(frame, columns=('Doba', 'Session'), show='headings')
        tree.heading('#0', text='Aplikace')
        tree.heading('Doba', text='Celková doba používání')
        tree.heading('Session', text='Počet session')
        tree.column('#0', width=200)

        for app, data in sorted(self.app_usage.items(), key=lambda x: x[1]['duration'], reverse=True):
            hours = data['duration'] / 3600
            tree.insert('', 'end', text=app, values=(f"{hours:.1f} hodin", len(data['sessions'])))
        
        tree.pack(fill='both', expand=True, padx=10, pady=10)

    def update_sleep_tab(self):
        self.clear_tab("😴 Spánek")
        frame = self.tabs["😴 Spánek"]
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        text.pack(fill='both', expand=True, padx=10, pady=10)
        text.insert(tk.END, "ANALÝZA SPÁNKU ZA 10 DNÍ\n", ('title',))
        
        current_date = None
        for event in self.power_events:
            if event['type'] not in ['sleep', 'wake']: continue
            event_date = event['time'].date()
            if event_date != current_date:
                current_date = event_date
                text.insert(tk.END, f"\n{event_date.strftime('%A %d.%m.%Y')}\n", ('date',))
            
            tag = 'sleep' if event['type'] == 'sleep' else 'wake'
            emoji = '😴' if event['type'] == 'sleep' else '⏰'
            text.insert(tk.END, f"  {emoji} {event['time'].strftime('%H:%M')} - {event['type'].capitalize()}\n", (tag,))
        
        text.tag_config('title', font=('Arial', 14, 'bold'))
        text.tag_config('date', font=('Arial', 12, 'bold'), foreground='blue')
        text.tag_config('sleep', foreground='gray')
        text.tag_config('wake', foreground='green')
        text.config(state='disabled')

    def update_stats_tab(self):
        self.clear_tab("📈 Statistiky")
        frame = self.tabs["📈 Statistiky"]
        stats_frame = ttk.LabelFrame(frame, text="Celkové statistiky za 10 dní", padding=20)
        stats_frame.pack(fill='both', expand=True, padx=20, pady=20)

        total_active = sum(s['duration'] for s in self.states if s['type'] == 'active') / 3600
        total_sleep = sum(s['duration'] for s in self.states if s['type'] == 'sleep') / 3600
        
        stats = [
            ('Celkem aktivní:', f"{total_active:.1f} hodin"),
            ('Celkem spánek:', f"{total_sleep:.1f} hodin"),
            ('', ''),
            ('Průměr aktivní/den:', f"{total_active/10:.1f} hodin"),
            ('Průměr spánek/den:', f"{total_sleep/10:.1f} hodin"),
        ]
        
        for i, (label, value) in enumerate(stats):
            ttk.Label(stats_frame, text=label).grid(row=i, column=0, sticky='w', pady=5)
            ttk.Label(stats_frame, text=value, font=('Arial', 12, 'bold')).grid(row=i, column=1, sticky='w', padx=10)

    def update_timeline_tab(self):
        self.clear_tab("🕒 Timeline")
        frame = self.tabs["🕒 Timeline"]
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        text.pack(fill='both', expand=True, padx=10, pady=10)

        all_events = self.power_events + self.app_events
        all_events.sort(key=lambda x: x['time'], reverse=True)

        current_date = None
        for event in all_events[:500]:
            event_date = event['time'].date()
            if event_date != current_date:
                current_date = event_date
                text.insert(tk.END, f"\n{event_date.strftime('%A %d.%m.%Y')}\n", ('date',))
            
            time_str = event['time'].strftime('%H:%M:%S')
            desc = event.get('app', event.get('description', 'N/A'))
            tag = 'app' if 'app' in event else 'power'
            text.insert(tk.END, f"{time_str} - {desc}\n", (tag,))
        
        text.tag_config('date', font=('Arial', 12, 'bold'), foreground='blue')
        text.tag_config('app', foreground='green')
        text.tag_config('power', foreground='orange')
        text.config(state='disabled')

    def update_finance_tab(self):
        self.clear_tab("💰 Finance")
        frame = self.tabs["💰 Finance"]
        
        settings_frame = ttk.LabelFrame(frame, text="Výpočet odměny", padding=20)
        settings_frame.pack(fill='x', padx=20, pady=20)
        
        ttk.Label(settings_frame, text="Hodinová sazba (Kč):").grid(row=0, column=0, sticky='w')
        self.rate_var = tk.StringVar(value=str(self.config_manager.config.get("hourly_rate", 250)))
        rate_entry = ttk.Entry(settings_frame, textvariable=self.rate_var, width=10)
        rate_entry.grid(row=0, column=1)
        ttk.Button(settings_frame, text="Přepočítat", command=self.calculate_finance).grid(row=0, column=2, padx=10)
        
        self.finance_result_frame = ttk.LabelFrame(frame, text="Výsledky", padding=20)
        self.finance_result_frame.pack(fill='both', expand=True, padx=20, pady=10)
        self.calculate_finance()

    def calculate_finance(self):
        for widget in self.finance_result_frame.winfo_children(): widget.destroy()
        try:
            rate = float(self.rate_var.get())
        except ValueError:
            rate = self.config_manager.config.get("hourly_rate", 250)

        active_hours = sum(s['duration'] for s in self.states if s['type'] == 'active') / 3600
        total_czk = active_hours * rate
        
        ttk.Label(self.finance_result_frame, text=f"Aktivních hodin: {active_hours:.1f} h").pack(anchor='w')
        ttk.Label(self.finance_result_frame, text=f"Celkem za 10 dní: {total_czk:,.0f} Kč").pack(anchor='w')

    def setup_settings_tab(self):
        self.clear_tab("⚙️ Nastavení")
        frame = self.tabs["⚙️ Nastavení"]
        
        apps_frame = ttk.LabelFrame(frame, text="Sledované aplikace", padding=10)
        apps_frame.pack(fill='x', padx=10, pady=10)

        self.apps_listbox = tk.Listbox(apps_frame, height=10)
        for app in self.config_manager.config.get("monitored_apps", []):
            self.apps_listbox.insert(tk.END, app)
        self.apps_listbox.pack(side='left', fill='both', expand=True)

        apps_buttons_frame = ttk.Frame(apps_frame)
        ttk.Button(apps_buttons_frame, text="➕ Přidat", command=self.add_app).pack(fill='x', pady=2)
        ttk.Button(apps_buttons_frame, text="➖ Odebrat", command=self.remove_app).pack(fill='x', pady=2)
        apps_buttons_frame.pack(side='left', padx=5)

        other_frame = ttk.LabelFrame(frame, text="Ostatní nastavení", padding=10)
        other_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(other_frame, text="Timeout session (minuty):").grid(row=0, column=0, sticky='w')
        self.session_timeout_var = tk.StringVar(value=str(self.config_manager.config.get("session_timeout_minutes", 30)))
        ttk.Entry(other_frame, textvariable=self.session_timeout_var, width=10).grid(row=0, column=1)

        ttk.Button(frame, text="💾 Uložit nastavení a obnovit analýzu", command=self.save_settings).pack(pady=20)

    def add_app(self):
        new_app = simpledialog.askstring("Přidat aplikaci", "Zadejte přesný název aplikace:")
        if new_app and new_app not in self.apps_listbox.get(0, tk.END):
            self.apps_listbox.insert(tk.END, new_app)

    def remove_app(self):
        selected_indices = self.apps_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Chyba", "Nejprve vyberte aplikaci k odebrání.")
            return
        for i in sorted(selected_indices, reverse=True):
            self.apps_listbox.delete(i)

    def save_settings(self):
        new_config = self.config_manager.config
        new_config["monitored_apps"] = list(self.apps_listbox.get(0, tk.END))
        try:
            new_config["hourly_rate"] = float(self.rate_var.get())
            new_config["session_timeout_minutes"] = int(self.session_timeout_var.get())
        except ValueError:
            messagebox.showerror("Chyba", "Hodinová sazba a timeout musí být čísla.")
            return

        self.config_manager.save_config(new_config)
        messagebox.showinfo("Uloženo", "Nastavení bylo uloženo. Spouštím novou analýzu.")
        self.analyze_activity()

    def export_data(self):
        from tkinter.filedialog import asksaveasfilename
        
        filename = asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"activity_export_{datetime.now().strftime('%Y-%m-%d')}.json"
        )
        
        if not filename: return
            
        data = {
            'exported_at': datetime.now().isoformat(),
            'app_usage': self.app_usage,
            'power_events': self.power_events,
            'activity_states': self.states,
        }
        
        def convert_dates(obj):
            if isinstance(obj, dict): return {k: convert_dates(v) for k, v in obj.items()}
            if isinstance(obj, list): return [convert_dates(item) for item in obj]
            if isinstance(obj, datetime): return obj.isoformat()
            return obj
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(convert_dates(data), f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Export", f"Data úspěšně exportována do:\n{filename}")
        except Exception as e:
            messagebox.showerror("Chyba exportu", f"Nepodařilo se exportovat data: {e}")


if __name__ == '__main__':
    root = tk.Tk()
    app = MacActivityAnalyzer(root)
    root.mainloop()