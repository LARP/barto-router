"""
test_qwen_inference.py — Validación de Inferencia Multi-Modelo (Qwen 2.5 1.5B)
"""
import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

payload = {
    "model": "qwen-2.5-1.5b",
    "messages": [
        {"role": "system", "content": "Eres un asistente experto en C# y Unity."},
        {"role": "user", "content": "Escribe una corrutina en C# para hacer un fade out del alpha de un CanvasGroup."}
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
print("[Cliente] Solicitando modelo Qwen 2.5 1.5B a través de barto-router...")

with urllib.request.urlopen(req, timeout=35) as resp:
    h = dict(resp.headers)
    print(f"[Router Header] Backend:  {h.get('X-Execution-Backend')}")
    print(f"[Router Header] Decisión: {h.get('X-Decision-Backend')}")
    print("\n--- RESPUESTA STREAMING DE QWEN 2.5 1.5B ---")
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

print("\n\n" + "=" * 55)
print(" MÉTRICAS DE INFERENCIA (QWEN 2.5 1.5B)")
print("=" * 55)
print(f"  TTFT (incluye auto-carga si estaba frío): {round((ttft or 0)*1000, 2)} ms")
print(f"  Tiempo total:                            {round(total_time, 2)} s")
print(f"  Tokens generados:                        {tokens}")
print(f"  Throughput real:                         {round(tps, 2)} t/s")
print("=" * 55)
