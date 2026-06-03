from __future__ import annotations
import subprocess
import logging
import re
import signal
import os
from typing import Callable
from src.core.exceptions import TerminalTimeOutError, TerminalCommandError

logger = logging.getLogger(__name__)
logger.propagate = True

TERMINAL_ERROR_PATTERNS = {
    r'===== Aborting =====': ('Error 01', 'Some lanes are not active'),
}


class Terminal:
    """
    Terminal manager basado en subprocess.

    El entorno (variables exportadas por setup.sh) se hereda automáticamente
    del proceso padre, ya que el contenedor Docker arranca con todo sourced.

    Usage:
        with Terminal(timeout=60, line_callback=my_fn) as term:
            output = term.run("CMSITminiDAQ -f /app/RD53A_GUI/fichero.xml",
                              cwd="/app/RD53A_GUI")
            output, pattern = term.run_scan("CMSITminiDAQ -f ...",
                                            cwd="/app/RD53A_GUI")

    line_callback: callable(str) invocado con cada línea de stdout en tiempo real.
    """

    def __init__(self, timeout: int = 30, verbose: bool = False,
                 line_callback: Callable[[str], None] | None = None):
        self.timeout = timeout
        self.verbose = verbose
        self.line_callback = line_callback
        self._proc: subprocess.Popen | None = None

        self.default_scan_end_patterns = [
            r'>>> Interfaces\s+destroyed <<<',
            r'@@@ End of CMSIT miniDAQ @@@',
        ]

        if verbose:
            logger.setLevel(logging.DEBUG)
            logger.handlers.clear()
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        else:
            logger.setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Estado y control
    # ------------------------------------------------------------------

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def kill(self):
        """Envía SIGINT al proceso en curso (equivalente a Ctrl+C)."""
        if self._proc and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            logger.debug("SIGINT sent to process")

    def close(self):
        """Termina el proceso en curso si sigue vivo."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            logger.debug("Process closed")
        self._proc = None

    # ------------------------------------------------------------------
    # Ejecución de comandos
    # ------------------------------------------------------------------

    def run(self, command: str, timeout: int | None = None,
            cwd: str | None = None) -> str:
        """
        Ejecuta un comando que termina solo y devuelve su stdout completo.
        Lanza TerminalTimeOutError si supera el timeout.
        Lanza TerminalCommandError si la salida contiene patrones de error conocidos.
        """
        cmd_timeout = timeout if timeout is not None else self.timeout
        logger.debug(f"run: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=cmd_timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            raise TerminalTimeOutError(command)

        output = result.stdout or ""
        self._check_for_errors(output)

        if self.verbose and output.strip():
            logger.info(f"Output:\n{output}")

        if self.line_callback:
            for line in output.splitlines():
                self._emit_line(line)

        return output.strip()

    def run_scan(self, command: str, timeout: int | None = None,
                 end_patterns: list[str] | None = None,
                 cwd: str | None = None) -> tuple[str, str | None]:
        """
        Ejecuta CMSITminiDAQ (u otro comando largo) leyendo stdout línea a
        línea hasta EOF. Devuelve (full_output, matched_pattern), donde
        matched_pattern es el primer patrón de fin encontrado, o None si el
        proceso acabó sin que apareciera ninguno (indicativo de error/abort).
        """
        patterns = end_patterns if end_patterns is not None else self.default_scan_end_patterns
        compiled = [re.compile(p) for p in patterns]
        cmd_timeout = timeout if timeout is not None else self.timeout

        logger.debug(f"run_scan: {command}")

        self._proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
        )

        full_output_lines: list[str] = []
        matched_pattern: str | None = None

        try:
            for raw_line in self._proc.stdout:
                line = raw_line.rstrip()
                full_output_lines.append(line)
                self._emit_line(line)

                if matched_pattern is None:
                    for i, pattern in enumerate(compiled):
                        if pattern.search(line):
                            matched_pattern = patterns[i]
                            logger.debug(f"End pattern matched: {matched_pattern}")
                            break

            # Esperar a que el proceso termine limpiamente
            try:
                self._proc.wait(timeout=cmd_timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                raise TerminalTimeOutError(command)

        finally:
            try:
                self._proc.stdout.close()
            except Exception:
                pass

        full_output = '\n'.join(full_output_lines)
        self._check_for_errors(full_output)

        if self.verbose and full_output.strip():
            logger.info(f"Output:\n{full_output}")

        return full_output, matched_pattern

    # ------------------------------------------------------------------
    # Alias para compatibilidad con callers existentes
    # ------------------------------------------------------------------

    def execute(self, command: str, timeout: int | None = None) -> str:
        return self.run(command, timeout)

    def execute_and_print(self, command: str, timeout: int | None = None):
        output = self.run(command, timeout)
        if output:
            logger.info(f"Output of '{command}':\n{output}")

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _check_for_errors(self, output: str):
        for pattern, (error_code, error_msg) in TERMINAL_ERROR_PATTERNS.items():
            if re.search(pattern, output):
                raise TerminalCommandError(error_code, error_msg, output)

    def _emit_line(self, line: str):
        if self.line_callback and line.strip():
            self.line_callback(line)