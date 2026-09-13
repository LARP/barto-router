"""
test_embeddings.py — Validación de Endpoint de Embeddings (Fase 16)
"""
import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

payload = {
    "input": "Optimización de shaders y render pipelines en Unity URP",
    "model": "bge-small"
}

req = urllib.request.Request(
    "http://127.0.0.1:9000/v1/embeddings",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
with urllib.request.urlopen(req, timeout=10) as resp:
    h = dict(resp.headers)
    data = json.loads(resp.read().decode("utf-8"))
    dt = (time.time() - t0) * 1000
    emb = data["data"][0]["embedding"]
    print("=" * 60)
    print(" [OK] EMBEDDING GENERADO EXITOSAMENTE A TRAVÉS DEL ROUTER")
    print("=" * 60)
    print(f"  Backend ejecutor:   {h.get('X-Execution-Backend')}")
    print(f"  Latencia total:     {dt:.2f} ms")
    print(f"  Dimensiones vector: {len(emb)}")
    print(f"  Primeros 4 floats:  {emb[:4]}")
    print("=" * 60)
