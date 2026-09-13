import sys
import os
import json
import socket
import urllib.request

ROUTER_HOST = "127.0.0.1"
ROUTER_PORT = 9000
ROUTER_URL = f"http://{ROUTER_HOST}:{ROUTER_PORT}/v1/chat/completions"

NODO_HOST = "192.168.100.105"
NODO_PORT = 8080
NODO_URL = f"http://{NODO_HOST}:{NODO_PORT}/v1/chat/completions"

def is_port_open(host, port, timeout=0.2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def get_best_endpoint():
    """Detecta de forma instantánea (<20ms) si el router local está activo, o va directo al nodo."""
    if is_port_open(ROUTER_HOST, ROUTER_PORT, timeout=0.2):
        return ROUTER_URL, "barto-router (127.0.0.1:9000)"
    if is_port_open(NODO_HOST, NODO_PORT, timeout=0.3):
        return NODO_URL, "Nodo Remoto GT 1030 (192.168.100.105:8080)"
    return None, None

def get_clipboard_text():
    """Obtiene el texto del portapapeles sin dependencias externas."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception as e:
        print(f"  [!] No se pudo leer el portapapeles: {e}")
        return None

def preguntar_stream(prompt, sistema="Eres un asistente experto en programación, Unity, C# y optimización de software."):
    endpoint_url, endpoint_name = get_best_endpoint()
    if not endpoint_url:
        print("\n[ERROR] No se pudo conectar ni con barto-router ni con el nodo remoto (192.168.100.105).")
        print("Verifica que el PC secundario esté encendido y conectado a la red LAN.")
        return

    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
        "stream": True
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        endpoint_url,
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )

    print(f"\n[{endpoint_name}]: ", end="", flush=True)

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            for line in response:
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str.startswith("data: ") and line_str != "data: [DONE]":
                    try:
                        chunk = json.loads(line_str[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            sys.stdout.write(content)
                            sys.stdout.flush()
                    except json.JSONDecodeError:
                        continue
        print("\n")
    except Exception as e:
        print(f"\n[!] Error en la respuesta: {e}\n")

def leer_multilinea(primer_linea=""):
    lineas = []
    if primer_linea:
        lineas.append(primer_linea)
    print("  [Modo multilínea activo. Pega tu código y escribe 'END' en una línea sola para enviar]")
    while True:
        try:
            linea = input("... ")
            if linea.strip() == "END":
                break
            lineas.append(linea)
        except EOFError:
            break
    return "\n".join(lineas)

def main():
    # Comprobación de conectividad inicial
    endpoint_url, endpoint_name = get_best_endpoint()
    
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        # Si el comando empieza con -local, --local o local
        if args[0].lower() in ["-local", "--local", "local"]:
            args = args[1:]
            if not args:
                # Si se llama solo '-local', usar el portapapeles si tiene texto
                clip = get_clipboard_text()
                if clip and clip.strip():
                    print(f"  [Enviando contenido copiado en portapapeles ({len(clip)} caracteres)...]")
                    preguntar_stream(clip)
                    return
                else:
                    print("Uso: chat -local <mensaje o pregunta>")
                    return

        arg_first = args[0]
        if os.path.isfile(arg_first):
            with open(arg_first, "r", encoding="utf-8", errors="replace") as f:
                pregunta = f"Analiza este archivo ({arg_first}):\n\n```\n{f.read()}\n```"
        else:
            pregunta = " ".join(args)
            
        preguntar_stream(pregunta)
        return

    print("=" * 68)
    print("      CHAT ASISTENTE DE IA LOCAL (barto-router / GT 1030)")
    print("=" * 68)
    if endpoint_name:
        print(f"  ● Conectado a: {endpoint_name}")
    else:
        print("  [!] Advertencia: No se detectó servicio activo en LAN.")
    print("\nComandos útiles:")
    print("  • /clip           : Pega el código de tu portapapeles")
    print("  • /code           : Entra en modo multilínea (finaliza con 'END')")
    print("  • /file <ruta>    : Lee y envía el contenido de un archivo directamente")
    print("  • 'salir'         : Terminar el chat")
    print("=" * 68 + "\n")

    while True:
        try:
            user_input = input("Tu > ")
            cmd = user_input.strip()

            if not cmd:
                continue

            if cmd.lower() in ["salir", "exit", "quit", "q"]:
                print("Hasta luego.")
                break

            # 1. Comando Portapapeles
            if cmd.lower() in ["/clip", "/pegar", "/paste"]:
                texto_clip = get_clipboard_text()
                if not texto_clip:
                    print("  [!] El portapapeles está vacío o no contiene texto.")
                    continue
                print(f"  [Portapapeles: {len(texto_clip)} caracteres]")
                pregunta = texto_clip

            # 2. Comando Archivo
            elif cmd.lower().startswith("/file "):
                filepath = cmd[6:].strip().strip('"').strip("'")
                if not os.path.isfile(filepath):
                    print(f"  [!] Archivo no encontrado: {filepath}")
                    continue
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    contenido = f.read()
                print(f"  [Archivo cargado: {filepath}]")
                pregunta = f"Analiza y optimiza el siguiente archivo ({os.path.basename(filepath)}):\n\n```\n{contenido}\n```"

            # 3. Modo Multilínea manual
            elif cmd.lower() in ["/code", "/multiline"] or cmd.startswith("```"):
                primer_linea = cmd if (cmd.startswith("```") and len(cmd) > 3) else ""
                pregunta = leer_multilinea(primer_linea)
                if not pregunta.strip():
                    continue

            # 4. Mensaje normal
            else:
                pregunta = user_input

            preguntar_stream(pregunta)

        except KeyboardInterrupt:
            print("\nSaliendo...")
            break

if __name__ == "__main__":
    main()
