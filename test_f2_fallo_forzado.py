"""F2 - Fallo forzado: NODO_SECUNDARIO caido -> fallback reactivo a LOCAL_RTX.
Lanza router sombra en 9001 con NODO apuntando a puerto muerto, LOCAL al real.
Criterio Etapa 9: recuperacion < 10s, X-Fallback=true, respuesta 200.
"""
import json, time, threading, urllib.request
from http.server import HTTPServer
import sys
sys.path.insert(0, ".")
from policy import PolicyEngine, CostEstimationPolicy, NodeStatus
import router as R

# Congelar decision en NODO para forzar el camino de fallo reactivo
engine_f2 = PolicyEngine(default_policy=CostEstimationPolicy(), enable_health_monitor=False)
engine_f2.backends["NODO_SECUNDARIO"].base_url = "http://127.0.0.1:59999"  # puerto muerto
engine_f2.backends["NODO_SECUNDARIO"].status = NodeStatus.ONLINE  # ONLINE para que decida NODO
engine_f2.backends["LOCAL_RTX"].base_url = "http://127.0.0.1:8081"
engine_f2.backends["LOCAL_RTX"].status = NodeStatus.ONLINE
R.engine = engine_f2  # inyectar en handler del router

srv = HTTPServer(("127.0.0.1", 19001), R.ModularRouterHandler)
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
time.sleep(0.5)

payload = {"model": "local",
           "messages": [{"role": "user", "content": "F2: di ok en una palabra."}],
           "max_tokens": 15, "stream": False}
t0 = time.time()
req = urllib.request.Request("http://127.0.0.1:19001/v1/chat/completions",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        elapsed = time.time() - t0
        h = dict(resp.headers)
        body = resp.read()[:200]
        print(f"F2 RESULT: status={resp.status} elapsed={elapsed:.2f}s")
        print(f"  X-Decision-Backend={h.get('X-Decision-Backend')}")
        print(f"  X-Execution-Backend={h.get('X-Execution-Backend')}")
        print(f"  X-Fallback={h.get('X-Fallback')}")
        print(f"  body={body!r}")
        ok = (resp.status == 200 and h.get("X-Fallback") == "true"
              and h.get("X-Execution-Backend") == "LOCAL_RTX" and elapsed < 10.0)
        print("F2 " + ("PASS (<10s, fallback reactivo OK)" if ok else "FAIL"))
finally:
    srv.shutdown()
