#!/usr/bin/env python3
"""
Log Parsers Module

Poskytuje robustní parsování systémových logů s podporou více formátů
a automatickou detekcí. Implementuje type-safe zpracování dat s validací.
"""

import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """Definice typů událostí"""
    # Power management
    SLEEP = "sleep"
    WAKE = "wake"
    DARK_WAKE = "dark_wake"
    MAINTENANCE_WAKE = "maintenance_wake"
    
    # System events
    BOOT = "boot"
    REBOOT = "reboot"
    SHUTDOWN = "shutdown"
    
    # Display events
    DISPLAY_ON = "display_on"
    DISPLAY_OFF = "display_off"
    
    # Lid events
    LID_OPEN = "lid_open"
    LID_CLOSE = "lid_close"
    
    # Power button
    POWER_BUTTON = "power_button"
    
    # App events
    ASSERTION_CREATE = "assertion_create"
    ASSERTION_RELEASE = "assertion_release"
    
    # Unknown
    UNKNOWN = "unknown"


class EventCategory(Enum):
    """Kategorie událostí"""
    POWER = "power"
    SYSTEM = "system"
    DISPLAY = "display"
    APPLICATION = "application"
    USER_ACTION = "user_action"
    OTHER = "other"


@dataclass
class ParsedEvent:
    """
    Datová struktura pro parsované události
    
    @description Type-safe reprezentace systémové události s validací
    """
    timestamp: datetime
    event_type: EventType
    category: EventCategory
    description: str
    raw_line: str
    details: Optional[Dict[str, Union[str, int, float]]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validace dat po inicializaci"""
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"Neplatný typ timestamp: {type(self.timestamp)}")
        
        if self.timestamp > datetime.now():
            raise ValueError("Timestamp nemůže být v budoucnosti")
        
        if not isinstance(self.event_type, EventType):
            raise ValueError(f"Neplatný typ události: {self.event_type}")
        
        if not isinstance(self.category, EventCategory):
            raise ValueError(f"Neplatná kategorie: {self.category}")
    
    def to_dict(self) -> Dict:
        """Konverze na slovník pro serializaci"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'category': self.category.value,
            'description': self.description,
            'raw_line': self.raw_line,
            'details': self.details
        }


class LogParser(ABC):
    """
    Abstraktní základní třída pro parsery logů
    
    @description Definuje rozhraní pro implementaci parserů různých formátů
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_parse(self, line: str) -> bool:
        """Určuje, zda parser dokáže zpracovat daný řádek"""
        pass
    
    @abstractmethod
    def parse(self, line: str) -> Optional[ParsedEvent]:
        """Parsuje řádek a vrací událost nebo None"""
        pass
    
    def parse_lines(self, lines: List[str]) -> List[ParsedEvent]:
        """
        Parsuje seznam řádků
        
        @param lines: Seznam řádků k parsování
        @returns: Seznam parsovaných událostí
        """
        events = []
        for line in lines:
            if line.strip() and self.can_parse(line):
                try:
                    event = self.parse(line)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.logger.debug(f"Chyba při parsování řádku: {e}")
        return events


class PmsetLogParser(LogParser):
    """
    Parser pro pmset logy s podporou více formátů
    
    @description Implementuje robustní parsování pmset logů s fallback mechanismy
    """
    
    # Definice formátů s prioritou
    TIMESTAMP_FORMATS = [
        {
            'name': 'standard',
            'pattern': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([+-]\d{4})',
            'date_format': '%Y-%m-%d %H:%M:%S',
            'has_timezone': True
        },
        {
            'name': 'standard_no_tz',
            'pattern': r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            'date_format': '%Y-%m-%d %H:%M:%S',
            'has_timezone': False
        },
        {
            'name': 'alternate',
            'pattern': r'(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',
            'date_format': '%a %b %d %H:%M:%S',
            'has_timezone': False
        }
    ]
    
    # Mapování vzorů na typy událostí
    EVENT_PATTERNS = {
        # Sleep events
        EventType.SLEEP: [
            r'Entering Sleep',
            r'Going to sleep',
            r'System Sleep'
        ],
        
        # Wake events
        EventType.WAKE: [
            r'Wake from Normal Sleep',
            r'Wake from sleep',
            r'System Wake'
        ],
        
        EventType.DARK_WAKE: [
            r'DarkWake from',
            r'DarkWake to FullWake'
        ],
        
        EventType.MAINTENANCE_WAKE: [
            r'Maintenance wake',
            r'Background wake'
        ],
        
        # Display events
        EventType.DISPLAY_ON: [
            r'Display is turned on',
            r'Display woke',
            r'Display on'
        ],
        
        EventType.DISPLAY_OFF: [
            r'Display is turned off',
            r'Display sleep',
            r'Display off'
        ],
        
        # Lid events
        EventType.LID_OPEN: [
            r'LidOpen',
            r'Lid opened'
        ],
        
        EventType.LID_CLOSE: [
            r'LidClose',
            r'Lid closed'
        ],
        
        # Power button
        EventType.POWER_BUTTON: [
            r'PowerButton',
            r'Power button'
        ],
        
        # System events
        EventType.SHUTDOWN: [
            r'Shutdown',
            r'System shutdown'
        ],
        
        # Assertions
        EventType.ASSERTION_CREATE: [
            r'Assertion created:',
            r'Created assertion'
        ],
        
        EventType.ASSERTION_RELEASE: [
            r'Assertion released:',
            r'Released assertion'
        ]
    }
    
    def can_parse(self, line: str) -> bool:
        """Kontroluje, zda řádek obsahuje parsovatelná data"""
        # Rychlá kontrola na přítomnost timestamp patternu
        for fmt in self.TIMESTAMP_FORMATS:
            if re.search(fmt['pattern'], line):
                return True
        return False
    
    def parse(self, line: str) -> Optional[ParsedEvent]:
        """Implementuje kaskádové parsování s více formáty"""
        # Pokus o extrakci timestamp
        timestamp, timezone = self._extract_timestamp(line)
        if not timestamp:
            return None
        
        # Detekce typu události
        event_type = self._detect_event_type(line)
        
        # Určení kategorie
        category = self._determine_category(event_type)
        
        # Extrakce detailů
        details = self._extract_details(line, event_type)
        
        # Vytvoření popisu
        description = self._create_description(event_type, details)
        
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            category=category,
            description=description,
            raw_line=line,
            details=details
        )
    
    def _extract_timestamp(self, line: str) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Extrahuje timestamp z řádku
        
        @returns: Tuple (timestamp, timezone)
        """
        for format_def in self.TIMESTAMP_FORMATS:
            match = re.search(format_def['pattern'], line)
            if match:
                try:
                    time_str = match.group(1)
                    timezone = match.group(2) if format_def['has_timezone'] and len(match.groups()) > 1 else None
                    
                    timestamp = datetime.strptime(time_str, format_def['date_format'])
                    
                    # Doplnění roku pro formáty bez roku
                    if timestamp.year == 1900:
                        current_year = datetime.now().year
                        timestamp = timestamp.replace(year=current_year)
                        
                        # Korekce pro události z minulého roku
                        if timestamp > datetime.now():
                            timestamp = timestamp.replace(year=current_year - 1)
                    
                    return timestamp, timezone
                    
                except Exception as e:
                    self.logger.debug(f"Parsování timestamp formátu {format_def['name']} selhalo: {e}")
                    continue
        
        return None, None
    
    def _detect_event_type(self, line: str) -> EventType:
        """Detekuje typ události na základě obsahu řádku"""
        for event_type, patterns in self.EVENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return event_type
        
        return EventType.UNKNOWN
    
    def _determine_category(self, event_type: EventType) -> EventCategory:
        """Určuje kategorii události"""
        category_mapping = {
            # Power events
            EventType.SLEEP: EventCategory.POWER,
            EventType.WAKE: EventCategory.POWER,
            EventType.DARK_WAKE: EventCategory.POWER,
            EventType.MAINTENANCE_WAKE: EventCategory.POWER,
            
            # System events
            EventType.BOOT: EventCategory.SYSTEM,
            EventType.REBOOT: EventCategory.SYSTEM,
            EventType.SHUTDOWN: EventCategory.SYSTEM,
            
            # Display events
            EventType.DISPLAY_ON: EventCategory.DISPLAY,
            EventType.DISPLAY_OFF: EventCategory.DISPLAY,
            
            # User actions
            EventType.LID_OPEN: EventCategory.USER_ACTION,
            EventType.LID_CLOSE: EventCategory.USER_ACTION,
            EventType.POWER_BUTTON: EventCategory.USER_ACTION,
            
            # App events
            EventType.ASSERTION_CREATE: EventCategory.APPLICATION,
            EventType.ASSERTION_RELEASE: EventCategory.APPLICATION,
            
            # Other
            EventType.UNKNOWN: EventCategory.OTHER
        }
        
        return category_mapping.get(event_type, EventCategory.OTHER)
    
    def _extract_details(self, line: str, event_type: EventType) -> Dict[str, Union[str, int, float]]:
        """Extrahuje dodatečné detaily z řádku"""
        details = {}
        
        # Wake reason
        if event_type in [EventType.WAKE, EventType.DARK_WAKE]:
            wake_match = re.search(r'Wake from.*?Reason:\s*([^\[]+)', line)
            if wake_match:
                details['wake_reason'] = wake_match.group(1).strip()
        
        # Sleep reason
        if event_type == EventType.SLEEP:
            if "Clamshell Sleep" in line:
                details['sleep_reason'] = "Clamshell"
            elif "Maintenance Sleep" in line:
                details['sleep_reason'] = "Maintenance"
            elif "Software Sleep" in line:
                details['sleep_reason'] = "Software"
            elif "Idle Sleep" in line:
                details['sleep_reason'] = "Idle"
        
        # Assertion details
        if event_type in [EventType.ASSERTION_CREATE, EventType.ASSERTION_RELEASE]:
            # Extract PID
            pid_match = re.search(r'PID\s+(\d+)', line)
            if pid_match:
                details['pid'] = int(pid_match.group(1))
            
            # Extract process name
            proc_match = re.search(r'PID\s+\d+\(([^)]+)\)', line)
            if proc_match:
                details['process'] = proc_match.group(1)
            
            # Extract assertion type
            type_match = re.search(r'(PreventUserIdleSystemSleep|PreventUserIdleDisplaySleep|PreventSystemSleep)', line)
            if type_match:
                details['assertion_type'] = type_match.group(1)
        
        # Duration for some events
        duration_match = re.search(r'Duration:\s*(\d+(?:\.\d+)?)\s*(?:secs?|seconds?)', line)
        if duration_match:
            details['duration'] = float(duration_match.group(1))
        
        return details
    
    def _create_description(self, event_type: EventType, details: Dict) -> str:
        """Vytváří čitelný popis události"""
        descriptions = {
            EventType.SLEEP: self._format_sleep_description(details),
            EventType.WAKE: self._format_wake_description(details),
            EventType.DARK_WAKE: "Probuzení na pozadí",
            EventType.MAINTENANCE_WAKE: "Probuzení pro údržbu",
            EventType.DISPLAY_ON: "Displej zapnut",
            EventType.DISPLAY_OFF: "Displej vypnut",
            EventType.LID_OPEN: "Víko otevřeno",
            EventType.LID_CLOSE: "Víko zavřeno",
            EventType.POWER_BUTTON: "Stisknuto tlačítko napájení",
            EventType.SHUTDOWN: "Vypnutí systému",
            EventType.BOOT: "Start systému",
            EventType.REBOOT: "Restart systému",
            EventType.ASSERTION_CREATE: self._format_assertion_description(details, True),
            EventType.ASSERTION_RELEASE: self._format_assertion_description(details, False),
            EventType.UNKNOWN: "Neznámá událost"
        }
        
        return descriptions.get(event_type, "Neznámá událost")
    
    def _format_sleep_description(self, details: Dict) -> str:
        """Formátuje popis události spánku"""
        reason = details.get('sleep_reason', 'Neznámý důvod')
        return f"Uspání systému ({reason})"
    
    def _format_wake_description(self, details: Dict) -> str:
        """Formátuje popis události probuzení"""
        reason = details.get('wake_reason', 'Neznámý důvod')
        return f"Probuzení systému ({reason})"
    
    def _format_assertion_description(self, details: Dict, is_create: bool) -> str:
        """Formátuje popis assertion události"""
        action = "vytvořena" if is_create else "uvolněna"
        process = details.get('process', 'Neznámý proces')
        assertion_type = details.get('assertion_type', 'Neznámý typ')
        return f"Power assertion {action}: {process} ({assertion_type})"


class LastCommandParser(LogParser):
    """
    Parser pro výstupy příkazů 'last reboot' a 'last shutdown'
    
    @description Parsuje historii bootů a shutdownů systému
    """
    
    # Format: reboot    ~                         Wed Oct 25 09:15
    LAST_PATTERN = r'^(reboot|shutdown)\s+~?\s+(.+?)\s+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2})'
    
    def can_parse(self, line: str) -> bool:
        """Kontroluje, zda řádek odpovídá formátu last příkazu"""
        return bool(re.match(self.LAST_PATTERN, line))
    
    def parse(self, line: str) -> Optional[ParsedEvent]:
        """Parsuje řádek z last příkazu"""
        match = re.match(self.LAST_PATTERN, line)
        if not match:
            return None
        
        event_name = match.group(1)
        console = match.group(2).strip()
        date_str = match.group(3)
        
        # Parse timestamp
        try:
            # Přidání roku
            current_year = datetime.now().year
            date_str_with_year = f"{current_year} {date_str}"
            timestamp = datetime.strptime(date_str_with_year, '%Y %a %b %d %H:%M')
            
            # Korekce roku pokud je timestamp v budoucnosti
            if timestamp > datetime.now():
                timestamp = timestamp.replace(year=current_year - 1)
        except ValueError:
            self.logger.debug(f"Nelze parsovat timestamp: {date_str}")
            return None
        
        # Určení typu události
        event_type = EventType.REBOOT if event_name == 'reboot' else EventType.SHUTDOWN
        
        # Vytvoření události
        return ParsedEvent(
            timestamp=timestamp,
            event_type=event_type,
            category=EventCategory.SYSTEM,
            description=f"Systém {'restartován' if event_type == EventType.REBOOT else 'vypnut'}",
            raw_line=line,
            details={'console': console if console != '~' else 'system'}
        )


class CompositeLogParser:
    """
    Kompozitní parser kombinující více parserů
    
    @description Orchestruje více parserů pro komplexní zpracování logů
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.parsers: List[LogParser] = [
            PmsetLogParser(logger=self.logger),
            LastCommandParser(logger=self.logger),
        ]
        self._stats = {parser.__class__.__name__: 0 for parser in self.parsers}
    
    def parse_content(self, content: str) -> List[ParsedEvent]:
        """
        Parsuje kompletní obsah logu
        
        @param content: Obsah logu k parsování
        @returns: Seznam parsovaných událostí seřazený podle času
        """
        events = []
        lines = content.split('\n')
        
        self.logger.info(f"Parsování {len(lines)} řádků logu")
        
        for line in lines:
            if not line.strip():
                continue
            
            parsed = False
            for parser in self.parsers:
                if parser.can_parse(line):
                    try:
                        event = parser.parse(line)
                        if event:
                            events.append(event)
                            self._stats[parser.__class__.__name__] += 1
                            parsed = True
                            break
                    except Exception as e:
                        self.logger.error(f"Chyba v parseru {parser.__class__.__name__}: {e}")
            
            if not parsed:
                self.logger.debug(f"Žádný parser nedokázal zpracovat: {line[:100]}")
        
        # Seřazení událostí podle času
        events.sort(key=lambda e: e.timestamp)
        
        self.logger.info(f"Naparsováno {len(events)} událostí")
        self.logger.debug(f"Statistiky parserů: {self._stats}")
        
        return events
    
    def add_parser(self, parser: LogParser) -> None:
        """
        Přidá nový parser
        
        @param parser: Instance parseru k přidání
        """
        self.parsers.append(parser)
        self._stats[parser.__class__.__name__] = 0
        self.logger.info(f"Přidán parser: {parser.__class__.__name__}")
    
    def get_stats(self) -> Dict[str, int]:
        """Vrací statistiky použití jednotlivých parserů"""
        return self._stats.copy()
    
    def clear_stats(self) -> None:
        """Vymaže statistiky"""
        for key in self._stats:
            self._stats[key] = 0


# Pomocné funkce

def filter_events_by_type(
    events: List[ParsedEvent], 
    event_types: List[EventType]
) -> List[ParsedEvent]:
    """
    Filtruje události podle typu
    
    @param events: Seznam událostí
    @param event_types: Typy událostí k zachování
    @returns: Filtrovaný seznam událostí
    """
    return [e for e in events if e.event_type in event_types]


def filter_events_by_timerange(
    events: List[ParsedEvent],
    start_time: datetime,
    end_time: Optional[datetime] = None
) -> List[ParsedEvent]:
    """
    Filtruje události podle časového rozsahu
    
    @param events: Seznam událostí
    @param start_time: Začátek časového rozsahu
    @param end_time: Konec časového rozsahu (None = nyní)
    @returns: Filtrovaný seznam událostí
    """
    if end_time is None:
        end_time = datetime.now()
    
    return [e for e in events if start_time <= e.timestamp <= end_time]


def group_events_by_day(events: List[ParsedEvent]) -> Dict[datetime, List[ParsedEvent]]:
    """
    Seskupuje události podle dne
    
    @param events: Seznam událostí
    @returns: Slovník den -> seznam událostí
    """
    from collections import defaultdict
    
    grouped = defaultdict(list)
    for event in events:
        day = event.timestamp.date()
        grouped[day].append(event)
    
    return dict(grouped)


# Ukázka použití
if __name__ == "__main__":
    # Nastavení loggeru
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Ukázková data
    sample_pmset_log = """
    2024-01-15 10:30:45 +0100 Sleep                 Entering Sleep state
    2024-01-15 14:15:22 +0100 Wake                  Wake from Normal Sleep [CDNVA] : due to UserActivity Assertion
    2024-01-15 14:15:23 +0100 Notification          Display is turned on
    2024-01-15 16:45:10 +0100 Assertions            PID 123(Safari) Created PreventUserIdleDisplaySleep
    """
    
    sample_last_log = """
    reboot    ~                         Mon Jan 15 09:00
    shutdown  ~                         Sun Jan 14 22:30
    """
    
    # Test kompozitního parseru
    parser = CompositeLogParser()
    
    # Parse pmset log
    events1 = parser.parse_content(sample_pmset_log)
    print(f"\nPmset události ({len(events1)}):")
    for event in events1:
        print(f"  {event.timestamp} - {event.event_type.value}: {event.description}")
    
    # Parse last log
    events2 = parser.parse_content(sample_last_log)
    print(f"\nLast události ({len(events2)}):")
    for event in events2:
        print(f"  {event.timestamp} - {event.event_type.value}: {event.description}")
    
    # Statistiky
    print(f"\nStatistiky parserů: {parser.get_stats()}")