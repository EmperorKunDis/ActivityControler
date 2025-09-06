#!/usr/bin/env python3
"""
Event Processor Module

Implementuje optimalizované zpracování událostí s podporou streamingu,
inkrementální analýzy a efektivního ukládání dat v paměti.
"""

import bisect
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Iterator, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import heapq

from log_parsers import ParsedEvent, EventType, EventCategory


class StateType(Enum):
    """Typy stavů systému"""
    ACTIVE = "active"
    PAUSE = "pause"
    SLEEP = "sleep"
    SHUTDOWN = "shutdown"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


@dataclass
class SystemState:
    """
    Reprezentace stavu systému v časovém intervalu
    
    @description Drží informaci o stavu systému mezi dvěma událostmi
    """
    start_time: datetime
    end_time: datetime
    state_type: StateType
    duration_seconds: float
    trigger_event: Optional[ParsedEvent] = None
    end_event: Optional[ParsedEvent] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validace a výpočet duration"""
        if self.end_time < self.start_time:
            raise ValueError("End time nemůže být před start time")
        
        if self.duration_seconds <= 0:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    @property
    def duration_minutes(self) -> float:
        """Vrací délku trvání v minutách"""
        return self.duration_seconds / 60
    
    @property
    def duration_hours(self) -> float:
        """Vrací délku trvání v hodinách"""
        return self.duration_seconds / 3600
    
    def overlaps_with(self, other: 'SystemState') -> bool:
        """Kontroluje, zda se stav překrývá s jiným stavem"""
        return not (self.end_time <= other.start_time or self.start_time >= other.end_time)


class StreamingEventProcessor:
    """
    Procesor událostí s podporou streamingu a inkrementálního zpracování
    
    @description Implementuje efektivní zpracování velkých objemů dat s minimální pamětovou náročností
    """
    
    def __init__(
        self,
        retention_days: int = 10,
        max_events: int = 10000,
        inactivity_threshold_seconds: int = 60,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializace procesoru s konfigurovatelnými limity
        
        @param retention_days: Počet dní pro uchování událostí
        @param max_events: Maximální počet událostí v paměti
        @param inactivity_threshold_seconds: Práh nečinnosti pro detekci pauzy
        @param logger: Logger instance
        """
        self.retention_threshold = datetime.now() - timedelta(days=retention_days)
        self.max_events = max_events
        self.inactivity_threshold = inactivity_threshold_seconds
        self.logger = logger or logging.getLogger(__name__)
        
        # Hlavní datové struktury
        self.events: Deque[ParsedEvent] = deque(maxlen=max_events)
        self.states: List[SystemState] = []
        
        # Indexy pro rychlé vyhledávání
        self._event_index: Dict[EventType, List[int]] = defaultdict(list)
        self._category_index: Dict[EventCategory, List[int]] = defaultdict(list)
        self._date_index: Dict[datetime.date, List[int]] = defaultdict(list)
        
        # Cache pro statistiky
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_valid = False
        
        # Callbacky pro inkrementální analýzu
        self._event_callbacks: List[Callable[[ParsedEvent], None]] = []
        self._state_callbacks: List[Callable[[SystemState], None]] = []
    
    def process_event_stream(self, event_generator: Iterator[ParsedEvent]) -> None:
        """
        Zpracovává stream událostí s průběžným filtrováním
        
        @param event_generator: Generator produkující události
        """
        self.logger.info("Zahájení zpracování event streamu")
        processed_count = 0
        
        for event in event_generator:
            if self._should_retain_event(event):
                self._add_event(event)
                self._analyze_state_change(event)
                self._trigger_callbacks(event)
                processed_count += 1
                
                if processed_count % 100 == 0:
                    self.logger.debug(f"Zpracováno {processed_count} událostí")
        
        # Finalizace stavů
        self._finalize_states()
        self.logger.info(f"Zpracování dokončeno, celkem {processed_count} událostí")
    
    def process_events_batch(self, events: List[ParsedEvent]) -> None:
        """
        Zpracovává batch událostí
        
        @param events: Seznam událostí k zpracování
        """
        # Seřazení podle času
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        # Zpracování jako stream
        self.process_event_stream(iter(sorted_events))
    
    def _should_retain_event(self, event: ParsedEvent) -> bool:
        """Určuje, zda událost splňuje kritéria pro uchování"""
        return (
            event.timestamp >= self.retention_threshold and
            event.event_type != EventType.UNKNOWN
        )
    
    def _add_event(self, event: ParsedEvent) -> None:
        """
        Přidává událost do kolekce s aktualizací indexů
        
        @param event: Událost k přidání
        """
        # Přidání do hlavní kolekce
        self.events.append(event)
        event_idx = len(self.events) - 1
        
        # Aktualizace indexů
        self._event_index[event.event_type].append(event_idx)
        self._category_index[event.category].append(event_idx)
        self._date_index[event.timestamp.date()].append(event_idx)
        
        # Invalidace cache
        self._stats_cache_valid = False
    
    def _analyze_state_change(self, event: ParsedEvent) -> None:
        """
        Analyzuje změnu stavu na základě nové události
        
        @param event: Nová událost
        """
        # Pokud nejsou žádné stavy, vytvoř první
        if not self.states:
            self._create_initial_state(event)
            return
        
        # Získání posledního stavu
        last_state = self.states[-1]
        
        # Detekce typu nového stavu
        new_state_type = self._determine_state_type(event)
        
        # Pokud je to stejný typ stavu, možná jen prodloužit
        if last_state.state_type == new_state_type and self._can_extend_state(last_state, event):
            self._extend_state(last_state, event)
        else:
            # Vytvoření nového stavu
            self._create_new_state(event, new_state_type)
    
    def _determine_state_type(self, event: ParsedEvent) -> StateType:
        """Určuje typ stavu na základě události"""
        # Mapování typů událostí na stavy
        state_mapping = {
            EventType.WAKE: StateType.ACTIVE,
            EventType.BOOT: StateType.ACTIVE,
            EventType.REBOOT: StateType.ACTIVE,
            EventType.DISPLAY_ON: StateType.ACTIVE,
            EventType.LID_OPEN: StateType.ACTIVE,
            EventType.POWER_BUTTON: StateType.ACTIVE,
            
            EventType.SLEEP: StateType.SLEEP,
            EventType.DISPLAY_OFF: StateType.SLEEP,
            EventType.LID_CLOSE: StateType.SLEEP,
            
            EventType.SHUTDOWN: StateType.SHUTDOWN,
            
            EventType.DARK_WAKE: StateType.MAINTENANCE,
            EventType.MAINTENANCE_WAKE: StateType.MAINTENANCE,
        }
        
        return state_mapping.get(event.event_type, StateType.UNKNOWN)
    
    def _can_extend_state(self, state: SystemState, event: ParsedEvent) -> bool:
        """
        Určuje, zda lze rozšířit existující stav
        
        @param state: Existující stav
        @param event: Nová událost
        @returns: True pokud lze stav rozšířit
        """
        # Časový rozdíl mezi koncem stavu a novou událostí
        time_diff = (event.timestamp - state.end_time).total_seconds()
        
        # Pro aktivní stav - pokud je časový rozdíl menší než práh nečinnosti
        if state.state_type == StateType.ACTIVE:
            return time_diff <= self.inactivity_threshold
        
        # Pro ostatní stavy - pouze pokud událost následuje bezprostředně
        return time_diff <= 1  # 1 sekunda tolerance
    
    def _extend_state(self, state: SystemState, event: ParsedEvent) -> None:
        """Rozšiřuje existující stav o novou událost"""
        state.end_time = event.timestamp
        state.end_event = event
        state.duration_seconds = (state.end_time - state.start_time).total_seconds()
    
    def _create_initial_state(self, event: ParsedEvent) -> None:
        """Vytváří počáteční stav"""
        state_type = self._determine_state_type(event)
        
        initial_state = SystemState(
            start_time=event.timestamp,
            end_time=event.timestamp + timedelta(seconds=1),  # Minimální délka
            state_type=state_type,
            duration_seconds=1,
            trigger_event=event
        )
        
        self.states.append(initial_state)
        self.logger.debug(f"Vytvořen počáteční stav: {state_type.value}")
    
    def _create_new_state(self, event: ParsedEvent, state_type: StateType) -> None:
        """
        Vytváří nový stav a ukončuje předchozí
        
        @param event: Událost triggující nový stav
        @param state_type: Typ nového stavu
        """
        if self.states:
            # Ukončení předchozího stavu
            last_state = self.states[-1]
            
            # Kontrola mezery mezi stavy
            gap_seconds = (event.timestamp - last_state.end_time).total_seconds()
            
            if gap_seconds > self.inactivity_threshold:
                # Vytvoření pause stavu pro mezeru
                if gap_seconds > 3600:  # Více než hodina
                    gap_type = StateType.SHUTDOWN
                elif gap_seconds > 600:  # Více než 10 minut
                    gap_type = StateType.SLEEP
                else:
                    gap_type = StateType.PAUSE
                
                gap_state = SystemState(
                    start_time=last_state.end_time,
                    end_time=event.timestamp,
                    state_type=gap_type,
                    duration_seconds=gap_seconds,
                    details={'inferred': True, 'gap_seconds': gap_seconds}
                )
                self.states.append(gap_state)
        
        # Vytvoření nového stavu
        new_state = SystemState(
            start_time=event.timestamp,
            end_time=event.timestamp + timedelta(seconds=1),
            state_type=state_type,
            duration_seconds=1,
            trigger_event=event
        )
        
        self.states.append(new_state)
        
        # Callback pro nový stav
        for callback in self._state_callbacks:
            try:
                callback(new_state)
            except Exception as e:
                self.logger.error(f"Chyba v state callback: {e}")
    
    def _finalize_states(self) -> None:
        """Finalizuje poslední stav"""
        if self.states and self.states[-1].end_time < datetime.now():
            # Rozšíření posledního stavu do současnosti
            self.states[-1].end_time = datetime.now()
            self.states[-1].duration_seconds = (
                self.states[-1].end_time - self.states[-1].start_time
            ).total_seconds()
    
    def _trigger_callbacks(self, event: ParsedEvent) -> None:
        """Spouští registrované callbacky pro událost"""
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Chyba v event callback: {e}")
    
    # Metody pro získávání dat
    
    def get_events_by_type(self, event_type: EventType) -> List[ParsedEvent]:
        """
        Efektivní získání událostí podle typu pomocí indexu
        
        @param event_type: Typ události
        @returns: Seznam událostí daného typu
        """
        indices = self._event_index.get(event_type, [])
        return [self.events[idx] for idx in indices if idx < len(self.events)]
    
    def get_events_by_date(self, date: datetime.date) -> List[ParsedEvent]:
        """
        Získání událostí pro konkrétní den
        
        @param date: Datum
        @returns: Seznam událostí z daného dne
        """
        indices = self._date_index.get(date, [])
        return [self.events[idx] for idx in indices if idx < len(self.events)]
    
    def get_states_by_type(self, state_type: StateType) -> List[SystemState]:
        """
        Získání stavů podle typu
        
        @param state_type: Typ stavu
        @returns: Seznam stavů daného typu
        """
        return [s for s in self.states if s.state_type == state_type]
    
    def get_states_for_date(self, date: datetime.date) -> List[SystemState]:
        """
        Získání stavů pro konkrétní den
        
        @param date: Datum
        @returns: Seznam stavů, které zasahují do daného dne
        """
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)
        
        return [
            s for s in self.states
            if not (s.end_time <= start_of_day or s.start_time >= end_of_day)
        ]
    
    # Statistické metody
    
    def calculate_statistics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Vypočítává komplexní statistiky
        
        @param force_refresh: Vynutit přepočet i když je cache platná
        @returns: Slovník se statistikami
        """
        if self._stats_cache_valid and not force_refresh:
            return self._stats_cache
        
        self.logger.info("Počítám statistiky...")
        
        stats = {
            'event_count': len(self.events),
            'state_count': len(self.states),
            'date_range': self._calculate_date_range(),
            'event_type_distribution': self._calculate_event_distribution(),
            'state_type_distribution': self._calculate_state_distribution(),
            'daily_stats': self._calculate_daily_stats(),
            'app_activity': self._calculate_app_activity(),
            'wake_reasons': self._calculate_wake_reasons(),
            'efficiency_metrics': self._calculate_efficiency_metrics()
        }
        
        self._stats_cache = stats
        self._stats_cache_valid = True
        
        return stats
    
    def _calculate_date_range(self) -> Dict[str, Optional[datetime]]:
        """Vypočítává časový rozsah dat"""
        if not self.events:
            return {'first': None, 'last': None, 'days': 0}
        
        first = min(e.timestamp for e in self.events)
        last = max(e.timestamp for e in self.events)
        days = (last.date() - first.date()).days + 1
        
        return {'first': first, 'last': last, 'days': days}
    
    def _calculate_event_distribution(self) -> Dict[str, int]:
        """Vypočítává distribuci typů událostí"""
        distribution = defaultdict(int)
        
        for event in self.events:
            distribution[event.event_type.value] += 1
        
        return dict(distribution)
    
    def _calculate_state_distribution(self) -> Dict[str, float]:
        """Vypočítává distribuci času v jednotlivých stavech"""
        distribution = defaultdict(float)
        
        for state in self.states:
            distribution[state.state_type.value] += state.duration_hours
        
        return dict(distribution)
    
    def _calculate_daily_stats(self) -> Dict[datetime.date, Dict[str, float]]:
        """Vypočítává denní statistiky"""
        daily_stats = {}
        
        # Seskupení stavů po dnech
        for date in self._date_index.keys():
            states = self.get_states_for_date(date)
            
            daily_stats[date] = {
                'active_hours': sum(s.duration_hours for s in states if s.state_type == StateType.ACTIVE),
                'pause_hours': sum(s.duration_hours for s in states if s.state_type == StateType.PAUSE),
                'sleep_hours': sum(s.duration_hours for s in states if s.state_type == StateType.SLEEP),
                'shutdown_hours': sum(s.duration_hours for s in states if s.state_type == StateType.SHUTDOWN),
                'maintenance_hours': sum(s.duration_hours for s in states if s.state_type == StateType.MAINTENANCE),
                'event_count': len(self.get_events_by_date(date))
            }
        
        return daily_stats
    
    def _calculate_app_activity(self) -> Dict[str, Dict[str, Any]]:
        """Vypočítává statistiky aplikací"""
        app_stats = defaultdict(lambda: {'assertion_count': 0, 'processes': set()})
        
        for event in self.events:
            if event.event_type in [EventType.ASSERTION_CREATE, EventType.ASSERTION_RELEASE]:
                process = event.details.get('process', 'Unknown')
                app_stats[process]['assertion_count'] += 1
                if 'pid' in event.details:
                    app_stats[process]['processes'].add(event.details['pid'])
        
        # Konverze setů na listy pro serializaci
        return {
            app: {
                'assertion_count': stats['assertion_count'],
                'unique_pids': len(stats['processes'])
            }
            for app, stats in app_stats.items()
        }
    
    def _calculate_wake_reasons(self) -> Dict[str, int]:
        """Analyzuje důvody probuzení"""
        reasons = defaultdict(int)
        
        for event in self.events:
            if event.event_type in [EventType.WAKE, EventType.DARK_WAKE]:
                reason = event.details.get('wake_reason', 'Unknown')
                reasons[reason] += 1
        
        return dict(reasons)
    
    def _calculate_efficiency_metrics(self) -> Dict[str, float]:
        """Vypočítává metriky efektivity"""
        total_hours = sum(s.duration_hours for s in self.states)
        active_hours = sum(s.duration_hours for s in self.states if s.state_type == StateType.ACTIVE)
        pause_hours = sum(s.duration_hours for s in self.states if s.state_type == StateType.PAUSE)
        
        productive_hours = active_hours + pause_hours
        
        return {
            'total_hours': total_hours,
            'active_hours': active_hours,
            'productive_hours': productive_hours,
            'efficiency_percent': (active_hours / productive_hours * 100) if productive_hours > 0 else 0,
            'average_active_duration_minutes': self._calculate_average_duration(StateType.ACTIVE),
            'average_pause_duration_minutes': self._calculate_average_duration(StateType.PAUSE)
        }
    
    def _calculate_average_duration(self, state_type: StateType) -> float:
        """Vypočítává průměrnou délku trvání stavu"""
        states = self.get_states_by_type(state_type)
        if not states:
            return 0.0
        
        return sum(s.duration_minutes for s in states) / len(states)
    
    # Registrace callbacků
    
    def register_event_callback(self, callback: Callable[[ParsedEvent], None]) -> None:
        """
        Registruje callback pro nové události
        
        @param callback: Funkce volaná pro každou novou událost
        """
        self._event_callbacks.append(callback)
    
    def register_state_callback(self, callback: Callable[[SystemState], None]) -> None:
        """
        Registruje callback pro nové stavy
        
        @param callback: Funkce volaná pro každý nový stav
        """
        self._state_callbacks.append(callback)
    
    # Export metody
    
    def export_events_json(self) -> List[Dict]:
        """Exportuje události jako JSON-serializable strukturu"""
        return [event.to_dict() for event in self.events]
    
    def export_states_json(self) -> List[Dict]:
        """Exportuje stavy jako JSON-serializable strukturu"""
        return [
            {
                'start_time': state.start_time.isoformat(),
                'end_time': state.end_time.isoformat(),
                'state_type': state.state_type.value,
                'duration_seconds': state.duration_seconds,
                'duration_hours': state.duration_hours,
                'trigger_event': state.trigger_event.to_dict() if state.trigger_event else None,
                'details': state.details
            }
            for state in self.states
        ]


# Ukázka použití
if __name__ == "__main__":
    # Nastavení loggeru
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Vytvoření procesoru
    processor = StreamingEventProcessor(
        retention_days=7,
        max_events=5000,
        inactivity_threshold_seconds=60
    )
    
    # Ukázková data
    from log_parsers import ParsedEvent
    
    sample_events = [
        ParsedEvent(
            timestamp=datetime.now() - timedelta(hours=2),
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="System wake",
            raw_line="Wake from sleep",
            details={'wake_reason': 'User Activity'}
        ),
        ParsedEvent(
            timestamp=datetime.now() - timedelta(hours=1, minutes=30),
            event_type=EventType.SLEEP,
            category=EventCategory.POWER,
            description="System sleep",
            raw_line="Entering sleep",
            details={'sleep_reason': 'Idle'}
        ),
        ParsedEvent(
            timestamp=datetime.now() - timedelta(minutes=30),
            event_type=EventType.WAKE,
            category=EventCategory.POWER,
            description="System wake",
            raw_line="Wake from sleep",
            details={'wake_reason': 'Power Button'}
        )
    ]
    
    # Zpracování událostí
    processor.process_events_batch(sample_events)
    
    # Výpis statistik
    stats = processor.calculate_statistics()
    print("\nStatistiky:")
    print(f"  Počet událostí: {stats['event_count']}")
    print(f"  Počet stavů: {stats['state_count']}")
    print(f"  Efektivita: {stats['efficiency_metrics']['efficiency_percent']:.1f}%")
    
    # Výpis stavů
    print("\nSystemové stavy:")
    for state in processor.states:
        print(f"  {state.start_time.strftime('%H:%M')} - {state.end_time.strftime('%H:%M')}: "
              f"{state.state_type.value} ({state.duration_minutes:.1f} minut)")