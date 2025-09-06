#!/usr/bin/env python3
"""
Secure Command Executor Module

Poskytuje bezpečné spouštění systémových příkazů s validací a whitelistem.
Eliminuje rizika shell injection a zajišťuje kontrolovaný přístup k systému.
"""

import subprocess
import logging
from typing import List, Dict, Optional, Tuple
import re
from pathlib import Path


class SecurityError(Exception):
    """Výjimka pro bezpečnostní problémy při spouštění příkazů"""
    pass


class SecureCommandExecutor:
    """
    Zabezpečená implementace spouštění systémových příkazů
    
    @description Třída implementující bezpečné spouštění příkazů s validací a whitelistem
    """
    
    # Definice povolených příkazů s jejich parametry
    ALLOWED_COMMANDS = {
        'pmset_log': {
            'command': ['pmset', '-g', 'log'],
            'allow_pipe': True,
            'description': 'Získání power management logů'
        },
        'pmset_assertions': {
            'command': ['pmset', '-g', 'assertions'],
            'allow_pipe': False,
            'description': 'Získání power assertions'
        },
        'last_reboot': {
            'command': ['last', 'reboot'],
            'allow_pipe': True,
            'description': 'Historie rebootů systému'
        },
        'last_shutdown': {
            'command': ['last', 'shutdown'],
            'allow_pipe': True,
            'description': 'Historie vypnutí systému'
        },
        'log_show': {
            'command': ['log', 'show'],
            'allow_pipe': True,
            'description': 'Zobrazení system logů',
            'allowed_args': ['--style', '--predicate', '--last']
        }
    }
    
    # Regex pro validaci argumentů
    SAFE_ARG_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_\./=":]+$')
    
    # Zakázané znaky v argumentech
    FORBIDDEN_CHARS = [';', '&', '|', '`', '$', '(', ')', '{', '}', '>', '<', '\n', '\r', '\\']
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inicializace executoru s volitelným loggerem
        
        @param logger: Logger instance pro logování operací
        """
        self.logger = logger or logging.getLogger(__name__)
        self._command_stats: Dict[str, int] = {}
    
    def execute_command(
        self, 
        command_key: str, 
        additional_args: Optional[List[str]] = None,
        timeout: int = 30,
        capture_stderr: bool = True
    ) -> Tuple[str, str, int]:
        """
        Bezpečné spuštění příkazu s validací proti whitelistu
        
        @param command_key: Klíč příkazu z definovaného whitelistu
        @param additional_args: Dodatečné argumenty pro příkaz
        @param timeout: Maximální doba běhu příkazu v sekundách
        @param capture_stderr: Zda zachytit stderr výstup
        @returns: Tuple (stdout, stderr, return_code)
        @raises SecurityError: Pokud příkaz není povolen nebo argumenty nejsou bezpečné
        """
        # Validace příkazu
        if command_key not in self.ALLOWED_COMMANDS:
            self.logger.error(f"Pokus o spuštění nepovoleného příkazu: {command_key}")
            raise SecurityError(f"Nepovolený příkaz: {command_key}")
        
        command_config = self.ALLOWED_COMMANDS[command_key]
        command = command_config['command'].copy()
        
        # Validace a přidání dodatečných argumentů
        if additional_args:
            validated_args = self._validate_arguments(additional_args, command_config)
            command.extend(validated_args)
        
        # Logování pokusu o spuštění
        self.logger.info(f"Spouštím příkaz: {command_key} s argumenty: {additional_args}")
        
        try:
            # Spuštění příkazu BEZ shell=True pro bezpečnost
            result = subprocess.run(
                command,
                shell=False,  # KRITICKÉ: Nikdy nepoužívat shell=True
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=self._get_safe_environment()
            )
            
            # Aktualizace statistik
            self._command_stats[command_key] = self._command_stats.get(command_key, 0) + 1
            
            # Logování výsledku
            if result.returncode == 0:
                self.logger.debug(f"Příkaz {command_key} úspěšně dokončen")
            else:
                self.logger.warning(
                    f"Příkaz {command_key} skončil s kódem: {result.returncode}"
                )
            
            return (
                result.stdout,
                result.stderr if capture_stderr else "",
                result.returncode
            )
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout při spuštění příkazu: {command_key}")
            raise SecurityError(f"Příkaz {command_key} překročil timeout {timeout}s")
        except Exception as e:
            self.logger.error(f"Chyba při spuštění příkazu {command_key}: {e}")
            raise SecurityError(f"Chyba při spuštění příkazu: {str(e)}")
    
    def execute_with_pipe(
        self,
        command_key: str,
        pipe_commands: List[Tuple[str, List[str]]],
        timeout: int = 30
    ) -> str:
        """
        Bezpečné spuštění příkazu s pipe do dalších příkazů (např. grep)
        
        @param command_key: Klíč hlavního příkazu
        @param pipe_commands: Seznam tuple (příkaz, argumenty) pro pipe
        @param timeout: Celkový timeout pro pipeline
        @returns: Výstup z pipeline
        @raises SecurityError: Pokud některý příkaz není bezpečný
        """
        # Ověření, že příkaz podporuje pipe
        if not self.ALLOWED_COMMANDS.get(command_key, {}).get('allow_pipe', False):
            raise SecurityError(f"Příkaz {command_key} nepodporuje pipe operace")
        
        # Whitelist povolených pipe příkazů
        allowed_pipe_commands = ['grep', 'tail', 'head', 'awk', 'sed']
        
        # Validace pipe příkazů
        for pipe_cmd, pipe_args in pipe_commands:
            if pipe_cmd not in allowed_pipe_commands:
                raise SecurityError(f"Nepovolený pipe příkaz: {pipe_cmd}")
            
            # Validace argumentů pipe příkazu
            for arg in pipe_args:
                if not self._is_safe_argument(arg):
                    raise SecurityError(f"Nebezpečný argument v pipe: {arg}")
        
        # Konstrukce pipeline
        processes = []
        
        try:
            # První příkaz
            stdout, _, _ = self.execute_command(command_key)
            
            # Aplikace pipe příkazů
            current_input = stdout
            for pipe_cmd, pipe_args in pipe_commands:
                cmd = [pipe_cmd] + pipe_args
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False
                )
                
                stdout, stderr = proc.communicate(input=current_input, timeout=timeout)
                
                if proc.returncode != 0:
                    self.logger.warning(
                        f"Pipe příkaz {pipe_cmd} skončil s kódem: {proc.returncode}"
                    )
                
                current_input = stdout
            
            return current_input
            
        except subprocess.TimeoutExpired:
            raise SecurityError("Pipeline překročila timeout")
        finally:
            # Cleanup procesů
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
    
    def _validate_arguments(
        self, 
        args: List[str], 
        command_config: Dict
    ) -> List[str]:
        """
        Validuje argumenty příkazu
        
        @param args: Seznam argumentů k validaci
        @param command_config: Konfigurace příkazu
        @returns: Validované argumenty
        @raises SecurityError: Pokud jsou argumenty nebezpečné
        """
        validated_args = []
        allowed_args = command_config.get('allowed_args', [])
        
        for arg in args:
            # Kontrola proti zakázaným znakům
            if not self._is_safe_argument(arg):
                raise SecurityError(f"Nebezpečný argument: {arg}")
            
            # Pokud jsou definovány povolené argumenty, kontrola proti nim
            if allowed_args:
                # Pro argumenty typu --key=value
                arg_key = arg.split('=')[0] if '=' in arg else arg
                if not any(arg_key.startswith(allowed) for allowed in allowed_args):
                    # Argument není klíč, může být hodnota
                    if validated_args and validated_args[-1] in allowed_args:
                        # Je to hodnota pro předchozí klíč
                        pass
                    else:
                        raise SecurityError(
                            f"Nepovolený argument: {arg} (povolené: {allowed_args})"
                        )
            
            validated_args.append(arg)
        
        return validated_args
    
    def _is_safe_argument(self, arg: str) -> bool:
        """
        Kontroluje, zda je argument bezpečný
        
        @param arg: Argument k kontrole
        @returns: True pokud je argument bezpečný
        """
        # Kontrola na prázdný argument
        if not arg:
            return False
        
        # Kontrola na zakázané znaky
        for char in self.FORBIDDEN_CHARS:
            if char in arg:
                self.logger.warning(f"Argument obsahuje zakázaný znak '{char}': {arg}")
                return False
        
        # Kontrola pomocí regex
        if not self.SAFE_ARG_PATTERN.match(arg):
            self.logger.warning(f"Argument neodpovídá bezpečnému patternu: {arg}")
            return False
        
        # Kontrola na path traversal
        if '..' in arg or arg.startswith('/etc/') or arg.startswith('/root/'):
            self.logger.warning(f"Potenciální path traversal: {arg}")
            return False
        
        return True
    
    def _get_safe_environment(self) -> Dict[str, str]:
        """
        Vytváří bezpečné prostředí pro spuštění příkazu
        
        @returns: Slovník s bezpečnými environment variables
        """
        import os
        
        # Vytvoření minimálního prostředí
        safe_env = {
            'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
            'LANG': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
            'HOME': os.environ.get('HOME', '/tmp'),
            'USER': os.environ.get('USER', 'nobody')
        }
        
        return safe_env
    
    def get_command_stats(self) -> Dict[str, int]:
        """
        Vrací statistiky spuštěných příkazů
        
        @returns: Slovník s počty spuštění jednotlivých příkazů
        """
        return self._command_stats.copy()
    
    def clear_stats(self) -> None:
        """Vymaže statistiky spuštěných příkazů"""
        self._command_stats.clear()
        self.logger.info("Statistiky příkazů vymazány")


# Pomocné funkce pro běžné operace

def get_pmset_logs(
    executor: SecureCommandExecutor, 
    grep_pattern: Optional[str] = None,
    tail_lines: int = 500
) -> str:
    """
    Získá pmset logy s volitelným filtrováním
    
    @param executor: Instance SecureCommandExecutor
    @param grep_pattern: Pattern pro grep filtrování
    @param tail_lines: Počet posledních řádků
    @returns: Filtrované logy
    """
    if grep_pattern:
        return executor.execute_with_pipe(
            'pmset_log',
            [
                ('grep', ['-E', grep_pattern]),
                ('tail', ['-n', str(tail_lines)])
            ]
        )
    else:
        stdout, _, _ = executor.execute_command('pmset_log')
        lines = stdout.split('\n')
        return '\n'.join(lines[-tail_lines:]) if lines else ""


def get_system_boots(executor: SecureCommandExecutor, limit: int = 20) -> str:
    """
    Získá historii bootů systému
    
    @param executor: Instance SecureCommandExecutor
    @param limit: Maximální počet záznamů
    @returns: Historie bootů
    """
    return executor.execute_with_pipe(
        'last_reboot',
        [('head', ['-n', str(limit)])]
    )


def get_system_shutdowns(executor: SecureCommandExecutor, limit: int = 20) -> str:
    """
    Získá historii vypnutí systému
    
    @param executor: Instance SecureCommandExecutor
    @param limit: Maximální počet záznamů
    @returns: Historie vypnutí
    """
    return executor.execute_with_pipe(
        'last_shutdown',
        [('head', ['-n', str(limit)])]
    )


# Ukázka použití
if __name__ == "__main__":
    # Nastavení loggeru
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Vytvoření executoru
    executor = SecureCommandExecutor()
    
    try:
        # Bezpečné získání pmset logů
        logs = get_pmset_logs(executor, grep_pattern="Wake|Sleep", tail_lines=10)
        print("Pmset logs:", logs[:200], "...")
        
        # Statistiky
        print("\nStatistiky příkazů:", executor.get_command_stats())
        
    except SecurityError as e:
        print(f"Bezpečnostní chyba: {e}")