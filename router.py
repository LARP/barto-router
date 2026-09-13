import json
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuraciones de endpoints
NODO_SECUNDARIO_URL = "http://192.168.100.105:8080"
LOCAL_HOST_URL = "http://127.0.0.1:8081" # llama-server local si se arranca en RTX 3050

# Umbrales del Router Adaptativo
MAX_PROMPT_CHARS_FOR_NODO = 3000   # ~1.000 - 1.500 tokens
MAX_GPU_UTIL_FOR_LOCAL = 15        # Si la RTX 3050 pasa del 15% (ej. Unity en Play), no usar local

def is_rtx_available():
    """Verifica si la RTX 3050 está en reposo (idle) para recibir cómputo de IA."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.free", "--format=csv,noheader,nounits"]
        output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
        util_str, free_mem_str = output.split(",")
        gpu_util = int(util_str.strip())
        free_mem = int(free_mem_str.strip())
        # Disponible si el uso es bajo y tiene al menos 3 GB de VRAM libre
        return gpu_util < MAX_GPU_UTIL_FOR_LOCAL and free_mem > 3000
    except Exception:
        return False

def decide_target(body_bytes):
    """
    Decide si la consulta va al Nodo Secundario (GT 1030) o al PC Principal (RTX 3050).
    """
    try:
        data = json.loads(body_bytes.decode("utf-8"))
        total_chars = 0
        for msg in data.get("messages", []):
            total_chars += len(msg.get("content", ""))

        # 1. Si el prompt es muy largo (supera umbral del nodo) y la RTX local está libre:
        # enviamos a RTX local (si está disponible el servicio local)
        if total_chars > MAX_PROMPT_CHARS_FOR_NODO and is_rtx_available():
            return "LOCAL_RTX", LOCAL_HOST_URL

        # 2. Por defecto: Proteger la GPU del PC Principal y enviar al Nodo Secundario
        return "NODO_SECUNDARIO", NODO_SECUNDARIO_URL
    except Exception:
        return "NODO_SECUNDARIO", NODO_SECUNDARIO_URL

class RouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Silenciar logs por defecto para consola limpia

    def do_GET(self):
        # Rutear peticiones GET (como /v1/models o /health)
        target_name, target_base = "NODO_SECUNDARIO", NODO_SECUNDARIO_URL
        target_url = f"{target_base}{self.path}"
        try:
            req = urllib.request.Request(target_url, headers=dict(self.headers))
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ["content-length", "transfer-encoding"]:
                        self.send_header(k, v)
                data = resp.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_error(502, f"Error conectando a backend ({target_name}): {e}")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        target_name, target_base = decide_target(body)
        target_url = f"{target_base}{self.path}"

        import time
        start_time = time.time()
        print(f"\n[barto-router] [INFO] Nueva consulta recibida ({content_length} bytes)", flush=True)
        print(f"               |-> Destino: {target_name}", flush=True)

        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=dict(self.headers),
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                elapsed = time.time() - start_time
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ["content-length", "transfer-encoding"]:
                        self.send_header(k, v)
                self.send_header("X-Processed-By", target_name)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                print(f"               |-> [OK] Respondido en {elapsed:.2f}s [{target_name}]", flush=True)
        except urllib.error.HTTPError as e:
            err_data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            # Fallback automático: si falló el primario, probar nodo secundario
            if target_base != NODO_SECUNDARIO_URL:
                print(f"[ROUTER] Reintentando por fallback en NODO_SECUNDARIO...")
                fallback_url = f"{NODO_SECUNDARIO_URL}{self.path}"
                try:
                    req_fb = urllib.request.Request(fallback_url, data=body, headers=dict(self.headers), method="POST")
                    with urllib.request.urlopen(req_fb, timeout=120) as resp:
                        self.send_response(resp.status)
                        for k, v in resp.getheaders():
                            if k.lower() not in ["content-length", "transfer-encoding"]:
                                self.send_header(k, v)
                        data = resp.read()
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                except Exception as fb_err:
                    self.send_error(502, f"Fallo primario y fallback: {fb_err}")
            else:
                self.send_error(502, f"Error conectando al nodo: {e}")

def run_router(port=9000):
    server = HTTPServer(("127.0.0.1", port), RouterHandler)
    print("=" * 65)
    print(f"  ROUTER ADAPTATIVO DE IA ACTIVO EN: http://127.0.0.1:{port}/v1")
    print(f"  • Nodo Secundario (Default/Proteccion GPU): {NODO_SECUNDARIO_URL}")
    print(f"  • Umbral de desvío automático: prompts > {MAX_PROMPT_CHARS_FOR_NODO} chars")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo Router...")
        server.server_close()

if __name__ == "__main__":
    run_router(port=9000)
