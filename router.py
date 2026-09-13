import json
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# CONFIGURACIÓN DEL ROUTER ADAPTATIVO
# ==========================================
NODO_SECUNDARIO_URL = "http://192.168.100.105:8080"
LOCAL_HOST_URL = "http://127.0.0.1:8081" # Si se levanta llama-server local en RTX 3050

# Umbrales de decisión
MAX_PROMPT_CHARS_FOR_NODO = 3000   # Prompts > 3000 caracteres se consideran "pesados"
MAX_GPU_UTIL_FOR_LOCAL = 15        # Si la RTX 3050 supera 15% de uso (ej. Unity en Play), se protege

def is_rtx_available():
    """Verifica si la RTX 3050 del PC Principal está en reposo con VRAM libre."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.free", "--format=csv,noheader,nounits"]
        output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
        util_str, free_mem_str = output.split(",")
        gpu_util = int(util_str.strip())
        free_mem = int(free_mem_str.strip())
        return gpu_util < MAX_GPU_UTIL_FOR_LOCAL and free_mem > 3000
    except Exception:
        return False

def decide_target(body_bytes):
    """Evalúa la carga y el tamaño del prompt para dirigir el tráfico."""
    try:
        data = json.loads(body_bytes.decode("utf-8"))
        total_chars = 0
        for msg in data.get("messages", []):
            total_chars += len(msg.get("content", ""))

        # Si el prompt es muy extenso y la RTX local está ociosa, derivar a local
        if total_chars > MAX_PROMPT_CHARS_FOR_NODO and is_rtx_available():
            return "LOCAL_RTX", LOCAL_HOST_URL

        # Caso habitual: derivar al nodo secundario para proteger el PC principal
        return "NODO_SECUNDARIO", NODO_SECUNDARIO_URL
    except Exception:
        return "NODO_SECUNDARIO", NODO_SECUNDARIO_URL

class RouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
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
            self.send_error(502, f"Error en backend ({target_name}): {e}")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        target_name, target_base = decide_target(body)
        target_url = f"{target_base}{self.path}"

        print(f"[barto-router] POST {self.path} ({content_length}B) -> Derivado a: {target_name}")

        try:
            req = urllib.request.Request(target_url, data=body, headers=dict(self.headers), method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ["content-length", "transfer-encoding"]:
                        self.send_header(k, v)
                data = resp.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            err_data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            # Fallback automático
            if target_base != NODO_SECUNDARIO_URL:
                print(f"[barto-router] Reintentando por fallback en NODO_SECUNDARIO...")
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
    print(f"  barto-router activo en: http://127.0.0.1:{port}/v1")
    print(f"  • Nodo Secundario (Default): {NODO_SECUNDARIO_URL}")
    print(f"  • Proteccion activa para GPU Principal RTX 3050")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo barto-router...")
        server.server_close()

if __name__ == "__main__":
    run_router(port=9000)
