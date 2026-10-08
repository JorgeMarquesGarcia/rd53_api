from __future__ import annotations
import subprocess
import logging
import re
import signal
from typing import Callable
from src.core.exceptions import TerminalTimeOutError, TerminalCommandError

logger = logging.getLogger(__name__)

TERMINAL_ERROR_PATTERNS = {
    r'===== Aborting =====': ('Error 01', 'Some lanes are not active'),
}
_COMPILED_ERROR_PATTERNS = [
    (re.compile(pattern), code, msg)
    for pattern, (code, msg) in TERMINAL_ERROR_PATTERNS.items()
]

DEFAULT_SCAN_END_PATTERNS = [
    r'>>> Interfaces\s+destroyed <<<',
    r'@@@ End of CMSIT miniDAQ @@@',
]

# Códigos de color ANSI que Ph2_ACF mete en sus logs (p. ej. "\033[1m\033[33m")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

# La salida del DAQ se decodifica como texto; un byte inválido no debe tumbar la lectura
_TEXT_OPTIONS = dict(text=True, encoding="utf-8", errors="replace")


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

    timeout: en run() es el tiempo máximo de ejecución del comando. En
    run_scan() es la espera máxima a que el proceso termine una vez cerrada
    su salida; el scan en sí no tiene límite (se para con send_enter()/kill()),
    así un scan largo nunca se corta a mitad. None = sin límite.
    """

    def __init__(self, timeout: int | None = 30, verbose: bool = False,
                 line_callback: Callable[[str], None] | None = None):
        self.timeout = timeout
        self.verbose = verbose
        self.line_callback = line_callback
        self._proc: subprocess.Popen | None = None
        self.default_scan_end_patterns = list(DEFAULT_SCAN_END_PATTERNS)

        if verbose:
            # Sin tocar handlers: los mensajes DEBUG suben por propagación
            logger.setLevel(logging.DEBUG)

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

    def send_enter(self) -> bool:
        """
        Envía un Enter (\\n) al stdin del proceso en curso.

        Es la manera limpia de parar CMSITminiDAQ en modo -t -1: el DAQ
        detecta el Enter, cierra el fichero .raw correctamente y termina.

        Returns:
            True si el Enter se envió con éxito, False si el proceso no
            estaba vivo o stdin no estaba disponible.
        """
        proc = self._proc
        if proc is not None and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write('\n')
                proc.stdin.flush()
                logger.debug("Enter sent to process stdin")
                return True
            except (OSError, ValueError) as e:   # ValueError: stdin ya cerrado
                logger.warning("send_enter failed: %s", e)
        return False

    def kill(self):
        """
        Envía SIGINT al proceso en curso (equivalente a Ctrl+C).

        Úsalo solo como fallback de emergencia. Para parar CMSITminiDAQ
        en modo standalone usa send_enter() para un cierre limpio del .raw.
        """
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
                logger.debug("SIGINT sent to process")
            except ProcessLookupError:   # terminó entre poll() y send_signal()
                pass

    def close(self):
        """Termina el proceso en curso si sigue vivo y libera sus pipes."""
        proc = self._proc
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                logger.debug("Process closed")
            self._close_pipes(proc)
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
        logger.debug("run: %s", command)

        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=cmd_timeout,
                cwd=cwd,
                **_TEXT_OPTIONS,
            )
        except subprocess.TimeoutExpired:
            raise TerminalTimeOutError(command) from None

        output = result.stdout or ""
        self._check_for_errors(output)

        if self.verbose and output.strip():
            logger.info("Output:\n%s", output)

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

        logger.debug("run_scan: %s", command)

        proc = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            **_TEXT_OPTIONS,
        )
        self._proc = proc

        full_output_lines: list[str] = []
        matched_pattern: str | None = None

        try:
            for raw_line in proc.stdout:
                line = raw_line.rstrip()
                full_output_lines.append(line)
                self._emit_line(line)

                if matched_pattern is None:
                    for pattern, regex in zip(patterns, compiled):
                        if regex.search(line):
                            matched_pattern = pattern
                            logger.debug("End pattern matched: %s", matched_pattern)
                            break

            # Esperar a que el proceso termine limpiamente
            try:
                proc.wait(timeout=cmd_timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise TerminalTimeOutError(command) from None

        finally:
            self._close_pipes(proc)

        full_output = '\n'.join(full_output_lines)
        self._check_for_errors(full_output)

        if self.verbose and full_output.strip():
            logger.info("Output:\n%s", full_output)

        return full_output, matched_pattern

    # ------------------------------------------------------------------
    # Alias para compatibilidad con callers existentes
    # ------------------------------------------------------------------

    def execute(self, command: str, timeout: int | None = None) -> str:
        return self.run(command, timeout)

    def execute_and_print(self, command: str, timeout: int | None = None):
        output = self.run(command, timeout)
        if output:
            logger.info("Output of '%s':\n%s", command, output)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _close_pipes(proc: subprocess.Popen) -> None:
        for pipe in (proc.stdin, proc.stdout):
            if pipe is not None:
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass

    def _check_for_errors(self, output: str):
        for regex, error_code, error_msg in _COMPILED_ERROR_PATTERNS:
            if regex.search(output):
                raise TerminalCommandError(error_code, error_msg, output)

    def _emit_line(self, line: str):
        if self.line_callback and line.strip():
            self.line_callback(line)
