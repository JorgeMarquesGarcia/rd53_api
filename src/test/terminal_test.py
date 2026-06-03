#!/usr/bin/env python3
"""
Terminal Test Script usando pexpect
Permite ejecutar comandos en una terminal interactiva
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rd53_api.remote.terminal import Terminal
from rd53_api.core.exceptions import TerminalCommandError



def main():
    """Función principal con ejemplos de uso"""
    
    # Método 1: Usando context manager CON VERBOSE (recomendado para debug)
    print("=== Test 1: Context Manager (verbose=True para ver todo) ===")
    with Terminal(timeout=60, verbose=True) as term:
        # Ejemplo 1: Cambiar de directorio
        term.cd("/app/Ph2_ACF")
        
        # Ejemplo 2: Verificar el directorio actual
        output = term.run("pwd")
        print(f"Current directory: {output}")
        
        # Ejemplo 3: Listar archivos
        output = term.run("ls -la")
        print(f"Files:\n{output[:200]}...")  # Primeros 200 chars
        
        # Ejemplo 4: Source script
        term.source("setup.sh")
        print("Script sourced successfully")
        
        # Ejemplo 5: Navegar y ejecutar comando complejo
        term.cd("/app/Ph2_ACF/RD53_QUAD/")
        output = term.run("ls -la")
        print(f"RD53_QUAD files:\n{output[:200]}...")
    
    print("\n=== Test 2: Manual open/close ===")
    # Método 2: Manual (para control explícito)
    terminal = Terminal(timeout=60)
    
    try:
        terminal.open()
        
        # Verificar que está vivo
        if terminal.is_alive():
            print("✓ Terminal is alive")
        
        # Ejecutar comando
        output = terminal.run("echo 'Hello from manual terminal'")
        print(f"Output: {output}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        terminal.close()
        print("✓ Terminal closed manually")
    
    print("\n=== Test 3: Error Detection (TerminalCommandError) ===")
    # Método 3: Captura de errores de terminal
    print("Este test demuestra cómo capturar errores específicos detectados en el output")
    print("Patrones de error configurados:")
    from rd53_api.remote.terminal import TERMINAL_ERROR_PATTERNS
    for pattern, (code, msg) in TERMINAL_ERROR_PATTERNS.items():
        print(f"  • {code}: {msg}")
    
    with Terminal(timeout=30, verbose=True) as term:
        try:
            # Este es un ejemplo - en la práctica ocurriría con comandos reales
            # que retornen el patrón de error
            print("\n✓ Terminal ready to detect errors")
            print("  Si un comando devuelve: |HH:MM:SS|E|===== Aborting =====")
            print("  Se lanzará automáticamente: TerminalCommandError('Error 01', 'Some lanes are not active')")
            
            # Ejemplo: intentar ejecutar un comando que podría fallar
            output = term.run("echo 'Test command'")
            print(f"\n✓ Command successful: {output}")
            
        except TerminalCommandError as e:
            print(f"\n❌ TerminalCommandError caught!")
            print(f"   Code: {e.error_code}")
            print(f"   Message: {e.error_msg}")
            print(f"   Full output:\n{e.output}")
        
        except Exception as e:
            print(f"❌ Other error: {type(e).__name__}: {e}")
    
    print("\n=== All tests completed ===")



if __name__ == "__main__":
    main()