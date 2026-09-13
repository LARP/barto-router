import sys
import json
import time
import uuid
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

from policy import PolicyEngine, ThresholdPolicy, NodeStatus
from telemetry import TelemetryLogger, TelemetryRecord

# Inicializar motor de políticas y logger de telemetría
engine = PolicyEngine(default_policy=ThresholdPolicy())
telemetry = TelemetryLogger("telemetry.jsonl")

class ModularRouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Consola limpia

    def do_GET(self):
        # 1. Endpoint de Telemetría interna
        if self.path in ["/telemetry", "/telemetry/"]:
            try:
                records = []
                if sys.platform:
                    try:
                        with open("telemetry.jsonl", "r", encoding="utf-8") as f:
                            for line in f.readlines()[-20:]: # Últimos 20 registros
                                if line.strip():
                                    records.append(json.loads(line))
                    except FileNotFoundError:
                        pass
                data = json.dumps({"status": "ok", "recent_requests": records}, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                self.send_error(500, f"Error leyendo telemetria: {e}")
                return

        # 2. Endpoint Health check en vivo con latencias y estado
        if self.path in ["/health", "/health/"]:
            summary = engine.get_status_summary()
            summary["status"] = "ok"
            body = json.dumps(summary, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 3. Proxear peticiones GET (como /v1/models) al nodo secundario por defecto
        target_backend = engine.get_backend("NODO_SECUNDARIO")
        target_url = f"{target_backend.base_url}{self.path}"
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
            self.send_error(502, f"Error conectando a backend ({target_backend.name}): {e}")

    def do_POST(self):
        req_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Parsear payload para la Policy
        req_json = {}
        try:
            req_json = json.loads(body.decode("utf-8"))
        except Exception:
            pass

        # 1. Consultar a PolicyEngine
        selected_backend, decision_reason = engine.decide(req_json)
        prompt_chars = sum(len(m.get("content", "")) for m in req_json.get("messages", []) if isinstance(m, dict))
        
        record = TelemetryRecord(
            request_id=req_id,
            policy_name=engine.policy.name,
            decision_backend=selected_backend.name,
            decision_reason=decision_reason,
            prompt_chars=prompt_chars
        )

        print(f"\n[ROUTER-{req_id}] Nueva petición ({content_length} bytes)")
        print(f"            |-> Decisión: {selected_backend.name} ({decision_reason})")

        # 2. Despachar petición con soporte de fallback
        target_url = f"{selected_backend.base_url}{self.path}"
        executed_backend = selected_backend
        fallback_occurred = False
        fallback_reason = None
        resp_data = None
        status_code = 200

        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=dict(self.headers),
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                status_code = resp.status
                resp_data = resp.read()
        except Exception as primary_err:
            # Fallback automático
            fallback_backend_name = "NODO_SECUNDARIO" if selected_backend.name == "LOCAL_RTX" else "LOCAL_RTX"
            fallback_backend = engine.get_backend(fallback_backend_name)
            print(f"[ROUTER-{req_id}] [!] Fallo en {selected_backend.name}: {primary_err}")
            print(f"            |-> Activando Fallback a: {fallback_backend.name}...")
            
            fallback_url = f"{fallback_backend.base_url}{self.path}"
            try:
                fb_req = urllib.request.Request(
                    fallback_url,
                    data=body,
                    headers=dict(self.headers),
                    method="POST"
                )
                with urllib.request.urlopen(fb_req, timeout=120) as fb_resp:
                    status_code = fb_resp.status
                    resp_data = fb_resp.read()
                    executed_backend = fallback_backend
                    fallback_occurred = True
                    fallback_reason = f"Fallo en {selected_backend.name}: {primary_err}"
            except Exception as fb_err:
                elapsed_ms = (time.time() - start_time) * 1000
                record.finalize(
                    execution_backend=selected_backend.name,
                    total_time_ms=elapsed_ms,
                    success=False,
                    error_message=f"Fallo primario ({primary_err}) y fallback ({fb_err})"
                )
                telemetry.log(record)
                self.send_error(502, f"Fallo primario y fallback: {fb_err}")
                return

        # 3. Finalizar métricas y responder al cliente
        elapsed_ms = (time.time() - start_time) * 1000
        p_tokens = 0
        c_tokens = 0
        try:
            res_obj = json.loads(resp_data.decode("utf-8"))
            usage = res_obj.get("usage", {})
            p_tokens = usage.get("prompt_tokens", 0)
            c_tokens = usage.get("completion_tokens", 0)
        except Exception:
            pass

        record.finalize(
            execution_backend=executed_backend.name,
            total_time_ms=elapsed_ms,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            success=True,
            fallback_occurred=fallback_occurred,
            fallback_reason=fallback_reason
        )
        telemetry.log(record)

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-ID", req_id)
        self.send_header("X-Decision-Backend", selected_backend.name)
        self.send_header("X-Execution-Backend", executed_backend.name)
        self.send_header("X-Fallback", "true" if fallback_occurred else "false")
        self.send_header("X-Total-Time-Ms", str(round(elapsed_ms, 2)))
        self.send_header("Content-Length", str(len(resp_data)))
        self.end_headers()
        self.wfile.write(resp_data)
        
        print(f"            |-> [OK] Ejecutado en {executed_backend.name} en {elapsed_ms/1000.0:.2f}s "
              f"({c_tokens} tokens generados) | Fallback: {fallback_occurred}")

def run_server(port=9000):
    server = HTTPServer(("127.0.0.1", port), ModularRouterHandler)
    print("=" * 68)
    print(f"  BARTO-ROUTER v0.2 (Modular: Router + PolicyEngine + Telemetry)")
    print(f"  • Escuchando en: http://127.0.0.1:{port}/v1")
    print(f"  • Política Activa: {engine.policy.name}")
    print(f"  • Backends registrados:")
    for k, b in engine.backends.items():
        print(f"    - [{k}] -> {b.base_url}")
    print("=" * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo router...")
        server.server_close()

if __name__ == "__main__":
    run_server(port=9000)
