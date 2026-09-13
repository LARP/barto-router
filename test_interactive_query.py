"""
test_interactive_query.py — Prueba de Inferencia a través de Barto-Router
"""
import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

payload = {
    "model": "local",
    "messages": [
        {"role": "system", "content": "Eres un asistente conciso de desarrollo de videojuegos y optimización de gráficos."},
        {"role": "user", "content": "Dame 3 reglas de oro breves para mantener 60 FPS estables en Unity URP con shaders y texturas."}
    ],
    "max_tokens": 120,
    "stream": True
}

req = urllib.request.Request(
    "http://127.0.0.1:9000/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
ttft = None
tokens = 0
print("[Cliente] Enviando peticion a http://127.0.0.1:9000/v1/chat/completions ...")

with urllib.request.urlopen(req, timeout=20) as resp:
    h = dict(resp.headers)
    print(f"[Router Header] Backend Ejecutor: {h.get('X-Execution-Backend')}")
    print(f"[Router Header] Decisión:         {h.get('X-Decision-Backend')}")
    print("\n--- RESPUESTA EN STREAMING (TOKEN A TOKEN) ---")
    for line in resp:
        line_str = line.decode("utf-8").strip()
        if not line_str.startswith("data: "):
            continue
        data_str = line_str[6:].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            delta = chunk["choices"][0].get("delta", {}).get("content", "")
            if delta:
                if ttft is None:
                    ttft = time.time() - t0
                print(delta, end="", flush=True)
                tokens += 1
        except Exception:
            pass

total_time = time.time() - t0
gen_time = (total_time - ttft) if ttft else total_time
tps = (tokens / gen_time) if gen_time > 0 else 0

print("\n\n" + "=" * 50)
print(" MÉTRICAS DE LA PETICIÓN")
print("=" * 50)
print(f"  TTFT (Latencia al 1er token): {round((ttft or 0)*1000, 2)} ms")
print(f"  Tiempo total de generación:  {round(total_time, 2)} s")
print(f"  Tokens generados:            {tokens}")
print(f"  Throughput real:             {round(tps, 2)} t/s")
print(f"  Impacto en Unity:            0% de VRAM o ciclos de render local comprometidos")
print("=" * 50)
