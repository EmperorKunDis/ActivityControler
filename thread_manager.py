#!/usr/bin/env python3
"""
Thread Manager Module

Implementuje thread-safe správu vláken pro paralelní zpracování
s podporou graceful shutdown a monitoringu běžících úloh.
"""

import threading
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError
from typing import Dict, List, Callable, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import queue


class TaskStatus(Enum):
    """Stavy úlohy"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskInfo:
    """
    Informace o úloze
    
    @description Drží kompletní informace o běžící nebo dokončené úloze
    """
    task_id: str
    name: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[Exception] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Vrací dobu trvání úlohy v sekundách"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None
    
    @property
    def is_running(self) -> bool:
        """Určuje, zda úloha běží"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_finished(self) -> bool:
        """Určuje, zda je úloha dokončena (úspěšně nebo neúspěšně)"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                               TaskStatus.CANCELLED, TaskStatus.TIMEOUT]


class ThreadSafeAnalysisManager:
    """
    Thread-safe správce analýz s podporou zrušení a graceful shutdown
    
    @description Implementuje robustní správu vláken pro paralelní zpracování
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        default_timeout: float = 300,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializace správce s konfigurovatelným počtem workerů
        
        @param max_workers: Maximální počet paralelních workerů
        @param default_timeout: Výchozí timeout pro úlohy v sekundách
        @param logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        
        # Thread synchronization
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ActivityAnalyzer"
        )
        
        # Task tracking
        self._tasks: Dict[str, TaskInfo] = {}
        self._futures: Dict[str, Future] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        
        # Progress tracking
        self._progress_queue = queue.Queue()
        self._progress_thread = threading.Thread(
            target=self._progress_monitor,
            daemon=True
        )
        self._progress_thread.start()
        
        self.logger.info(f"ThreadSafeAnalysisManager inicializován s {max_workers} workery")
    
    def submit_task(
        self,
        func: Callable,
        *args,
        task_name: Optional[str] = None,
        task_id: Optional[str] = None,
        timeout: Optional[float] = None,
        on_complete: Optional[Callable[[TaskInfo], None]] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Odesílá úlohu k asynchronnímu zpracování
        
        @param func: Funkce k vykonání
        @param task_name: Lidsky čitelný název úlohy
        @param task_id: Unikátní ID úlohy (vygeneruje se pokud není zadáno)
        @param timeout: Timeout pro úlohu (použije default pokud není zadán)
        @param on_complete: Callback po dokončení úlohy
        @param on_progress: Callback pro progress updates
        @param metadata: Dodatečná metadata úlohy
        @returns: ID úlohy
        @raises RuntimeError: Pokud je manager ve stavu shutdown
        """
        if self._shutdown_event.is_set():
            raise RuntimeError("Manager je ve stavu shutdown")
        
        # Generování ID pokud není zadáno
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Kontrola duplicity
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"Úloha s ID {task_id} již existuje")
        
        # Vytvoření TaskInfo
        task_info = TaskInfo(
            task_id=task_id,
            name=task_name or func.__name__,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        # Wrapper pro zachycení výsledku a výjimek
        def task_wrapper():
            try:
                # Update stavu na RUNNING
                with self._lock:
                    task_info.status = TaskStatus.RUNNING
                    task_info.started_at = datetime.now()
                
                self.logger.info(f"Úloha {task_id} ({task_info.name}) zahájena")
                
                # Vytvoření progress reporteru pokud funkce podporuje
                if on_progress:
                    progress_reporter = self._create_progress_reporter(task_id, on_progress)
                    # Pokud funkce přijímá progress_callback, předáme ho
                    if 'progress_callback' in kwargs:
                        kwargs['progress_callback'] = progress_reporter
                
                # Spuštění funkce
                result = func(*args, **kwargs)
                
                # Update stavu na COMPLETED
                with self._lock:
                    task_info.status = TaskStatus.COMPLETED
                    task_info.completed_at = datetime.now()
                    task_info.result = result
                    task_info.progress = 1.0
                
                self.logger.info(f"Úloha {task_id} ({task_info.name}) dokončena úspěšně")
                
                return result
                
            except Exception as e:
                # Update stavu na FAILED
                with self._lock:
                    task_info.status = TaskStatus.FAILED
                    task_info.completed_at = datetime.now()
                    task_info.error = e
                
                self.logger.error(f"Úloha {task_id} ({task_info.name}) selhala: {str(e)}")
                raise
            
            finally:
                # Spuštění completion callbacku
                self._execute_callbacks(task_id, task_info)
        
        # Registrace úlohy
        with self._lock:
            self._tasks[task_id] = task_info
            
            # Registrace callbacků
            if on_complete:
                self._callbacks.setdefault(task_id, []).append(on_complete)
            
            # Submit do executoru
            future = self._executor.submit(task_wrapper)
            self._futures[task_id] = future
            
            # Nastavení timeoutu
            if timeout is None:
                timeout = self.default_timeout
            
            # Spuštění timeout watcheru
            if timeout > 0:
                self._start_timeout_watcher(task_id, timeout)
        
        self.logger.debug(f"Úloha {task_id} odeslána k zpracování")
        
        return task_id
    
    def cancel_task(self, task_id: str, force: bool = False) -> bool:
        """
        Pokouší se zrušit běžící úlohu
        
        @param task_id: ID úlohy k zrušení
        @param force: Vynutit zrušení i pokud úloha již běží
        @returns: True pokud byla úloha zrušena
        """
        with self._lock:
            if task_id not in self._tasks:
                self.logger.warning(f"Pokus o zrušení neexistující úlohy: {task_id}")
                return False
            
            task_info = self._tasks[task_id]
            future = self._futures.get(task_id)
            
            if not future:
                return False
            
            # Pokus o zrušení
            if future.cancel() or force:
                task_info.status = TaskStatus.CANCELLED
                task_info.completed_at = datetime.now()
                
                # Odstranění z futures
                self._futures.pop(task_id, None)
                
                # Spuštění callbacků
                self._execute_callbacks(task_id, task_info)
                
                self.logger.info(f"Úloha {task_id} byla zrušena")
                return True
            
            return False
    
    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """
        Získává informace o úloze
        
        @param task_id: ID úlohy
        @returns: TaskInfo nebo None pokud úloha neexistuje
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self, status_filter: Optional[TaskStatus] = None) -> List[TaskInfo]:
        """
        Získává seznam všech úloh
        
        @param status_filter: Volitelný filtr podle stavu
        @returns: Seznam TaskInfo objektů
        """
        with self._lock:
            tasks = list(self._tasks.values())
            
            if status_filter:
                tasks = [t for t in tasks if t.status == status_filter]
            
            return tasks
    
    def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        Čeká na dokončení úlohy
        
        @param task_id: ID úlohy
        @param timeout: Maximální doba čekání
        @returns: Tuple (success, result)
        """
        with self._lock:
            future = self._futures.get(task_id)
            if not future:
                task_info = self._tasks.get(task_id)
                if task_info and task_info.is_finished:
                    return (task_info.status == TaskStatus.COMPLETED, task_info.result)
                return (False, None)
        
        try:
            result = future.result(timeout=timeout)
            return (True, result)
        except TimeoutError:
            self.logger.warning(f"Timeout při čekání na úlohu {task_id}")
            return (False, None)
        except Exception as e:
            self.logger.error(f"Chyba při čekání na úlohu {task_id}: {str(e)}")
            return (False, None)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Získává aktuální stav správce
        
        @returns: Slovník se stavovými informacemi
        """
        with self._lock:
            task_stats = {
                'total': len(self._tasks),
                'pending': len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING]),
                'running': len([t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]),
                'completed': len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]),
                'failed': len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED]),
                'cancelled': len([t for t in self._tasks.values() if t.status == TaskStatus.CANCELLED])
            }
            
            return {
                'is_shutdown': self._shutdown_event.is_set(),
                'max_workers': self.max_workers,
                'task_stats': task_stats,
                'active_tasks': [
                    {
                        'task_id': tid,
                        'name': tinfo.name,
                        'duration': tinfo.duration,
                        'progress': tinfo.progress
                    }
                    for tid, tinfo in self._tasks.items()
                    if tinfo.is_running
                ]
            }
    
    def clear_finished_tasks(self) -> int:
        """
        Vymaže dokončené úlohy z paměti
        
        @returns: Počet vymazaných úloh
        """
        with self._lock:
            finished_tasks = [
                tid for tid, tinfo in self._tasks.items()
                if tinfo.is_finished
            ]
            
            for task_id in finished_tasks:
                self._tasks.pop(task_id, None)
                self._futures.pop(task_id, None)
                self._callbacks.pop(task_id, None)
            
            self.logger.info(f"Vymazáno {len(finished_tasks)} dokončených úloh")
            
            return len(finished_tasks)
    
    def shutdown(self, wait: bool = True, timeout: float = 30) -> None:
        """
        Graceful shutdown všech běžících úloh
        
        @param wait: Čekat na dokončení běžících úloh
        @param timeout: Maximální doba čekání na shutdown
        """
        self.logger.info("Zahajuji shutdown ThreadSafeAnalysisManager")
        
        # Nastavení shutdown flagu
        self._shutdown_event.set()
        
        # Zastavení progress monitoru
        if self._progress_thread.is_alive():
            self._progress_queue.put(None)  # Poison pill
            self._progress_thread.join(timeout=5)
        
        with self._lock:
            # Zrušení všech pending úloh
            for task_id, task_info in self._tasks.items():
                if task_info.status == TaskStatus.PENDING:
                    self.cancel_task(task_id)
            
            # Shutdown executoru
            self._executor.shutdown(wait=wait, timeout=timeout)
            
            # Označení běžících úloh jako timeout pokud wait=False
            if not wait:
                for task_id, task_info in self._tasks.items():
                    if task_info.is_running:
                        task_info.status = TaskStatus.TIMEOUT
                        task_info.completed_at = datetime.now()
        
        self.logger.info("Shutdown ThreadSafeAnalysisManager dokončen")
    
    def _create_progress_reporter(
        self,
        task_id: str,
        callback: Callable[[str, float], None]
    ) -> Callable[[float], None]:
        """
        Vytváří progress reporter pro úlohu
        
        @param task_id: ID úlohy
        @param callback: Callback pro progress updates
        @returns: Funkce pro reportování progressu
        """
        def report_progress(progress: float):
            """Reportuje progress úlohy"""
            progress = max(0.0, min(1.0, progress))  # Clamp to [0, 1]
            
            with self._lock:
                task_info = self._tasks.get(task_id)
                if task_info:
                    task_info.progress = progress
            
            # Přidání do fronty pro asynchronní zpracování
            self._progress_queue.put((task_id, progress, callback))
        
        return report_progress
    
    def _progress_monitor(self):
        """
        Monitor thread pro zpracování progress updates
        
        Běží v samostatném vlákně a volá progress callbacky
        """
        while not self._shutdown_event.is_set():
            try:
                # Čekání na progress update s timeoutem
                item = self._progress_queue.get(timeout=1.0)
                
                if item is None:  # Poison pill
                    break
                
                task_id, progress, callback = item
                
                try:
                    callback(task_id, progress)
                except Exception as e:
                    self.logger.error(f"Chyba v progress callbacku: {str(e)}")
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Chyba v progress monitoru: {str(e)}")
    
    def _start_timeout_watcher(self, task_id: str, timeout: float):
        """
        Spouští timeout watcher pro úlohu
        
        @param task_id: ID úlohy
        @param timeout: Timeout v sekundách
        """
        def timeout_handler():
            """Handler volaný při timeoutu"""
            time.sleep(timeout)
            
            with self._lock:
                task_info = self._tasks.get(task_id)
                if task_info and task_info.is_running:
                    self.logger.warning(f"Úloha {task_id} překročila timeout {timeout}s")
                    
                    # Pokus o zrušení
                    if self.cancel_task(task_id, force=True):
                        task_info.status = TaskStatus.TIMEOUT
                        task_info.error = TimeoutError(f"Úloha překročila timeout {timeout}s")
        
        # Spuštění timeout handleru v samostatném vlákně
        timeout_thread = threading.Thread(
            target=timeout_handler,
            daemon=True,
            name=f"Timeout-{task_id}"
        )
        timeout_thread.start()
    
    def _execute_callbacks(self, task_id: str, task_info: TaskInfo):
        """
        Spouští registrované callbacky pro úlohu
        
        @param task_id: ID úlohy
        @param task_info: Informace o úloze
        """
        callbacks = self._callbacks.get(task_id, [])
        
        for callback in callbacks:
            try:
                # Spuštění callbacku v samostatném vlákně pro izolaci
                callback_thread = threading.Thread(
                    target=callback,
                    args=(task_info,),
                    daemon=True,
                    name=f"Callback-{task_id}"
                )
                callback_thread.start()
            except Exception as e:
                self.logger.error(f"Chyba při spuštění callbacku pro {task_id}: {str(e)}")


# Pomocné funkce

def create_progress_tracker() -> Tuple[Callable[[float], None], Callable[[], float]]:
    """
    Vytváří thread-safe progress tracker
    
    @returns: Tuple (update_progress, get_progress)
    """
    progress = 0.0
    lock = threading.Lock()
    
    def update_progress(value: float):
        nonlocal progress
        with lock:
            progress = max(0.0, min(1.0, value))
    
    def get_progress() -> float:
        with lock:
            return progress
    
    return update_progress, get_progress


# Ukázka použití
if __name__ == "__main__":
    # Nastavení loggeru
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Vytvoření manageru
    manager = ThreadSafeAnalysisManager(max_workers=2)
    
    # Ukázková úloha s progress reportingem
    def sample_task(duration: int, progress_callback: Callable[[float], None] = None):
        """Ukázková úloha simulující práci"""
        steps = 10
        for i in range(steps):
            time.sleep(duration / steps)
            if progress_callback:
                progress_callback((i + 1) / steps)
        return f"Completed after {duration}s"
    
    # Callback pro dokončení
    def on_task_complete(task_info: TaskInfo):
        print(f"Úloha {task_info.name} dokončena se stavem: {task_info.status.value}")
        if task_info.result:
            print(f"  Výsledek: {task_info.result}")
        if task_info.error:
            print(f"  Chyba: {task_info.error}")
    
    # Callback pro progress
    def on_progress(task_id: str, progress: float):
        print(f"Progress {task_id}: {progress * 100:.1f}%")
    
    # Submit úloh
    task1_id = manager.submit_task(
        sample_task,
        3,
        task_name="Rychlá úloha",
        on_complete=on_task_complete,
        on_progress=on_progress
    )
    
    task2_id = manager.submit_task(
        sample_task,
        5,
        task_name="Pomalá úloha",
        on_complete=on_task_complete,
        timeout=2  # Způsobí timeout
    )
    
    # Čekání chvilku
    time.sleep(1)
    
    # Výpis stavu
    print("\nStav manageru:")
    status = manager.get_status()
    print(f"  Běžící úlohy: {status['task_stats']['running']}")
    print(f"  Aktivní úlohy: {status['active_tasks']}")
    
    # Čekání na dokončení
    time.sleep(6)
    
    # Finální stav
    print("\nFinální stav:")
    for task in manager.get_all_tasks():
        print(f"  {task.name}: {task.status.value} (trvání: {task.duration:.1f}s)")
    
    # Shutdown
    manager.shutdown()