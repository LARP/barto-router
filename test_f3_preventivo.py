import json, time, threading, urllib.request
from http.server import HTTPServer
from policy import PolicyEngine, CostEstimationPolicy, NodeStatus
import router as R

engine_f3 = PolicyEngine(default_policy=CostEstimationPolicy(), enable_health_monitor=False)
engine_f3.backends["NODO_SECUNDARIO"].status = NodeStatus.OFFLINE
engine_f3.backends["LOCAL_RTX"].status = NodeStatus.ONLINE
engine_f3.backends["LOCAL_RTX"].base_url = "http://127.0.0.1:8081"
R.engine = engine_f3
srv = HTTPServer(("127.0.0.1", 19002), R.ModularRouterHandler)
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
time.sleep(0.5)
p = {"model": "local", "messages": [{"role": "user", "content": "F3: di ok."}],
     "max_tokens": 15, "stream": False}
t0 = time.time()
req = urllib.request.Request("http://127.0.0.1:19002/v1/chat/completions",
    data=json.dumps(p).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as resp:
    el = time.time() - t0
    h = dict(resp.headers)
    body = resp.read()[:150]
    print(f"F3 RESULT: status={resp.status} elapsed={el:.2f}s")
    print(f"  X-Decision={h.get('X-Decision-Backend')} X-Exec={h.get('X-Execution-Backend')} X-Fallback={h.get('X-Fallback')}")
    print(f"  body={body!r}")
    ok = (resp.status == 200 and h.get("X-Decision-Backend") == "LOCAL_RTX"
          and h.get("X-Execution-Backend") == "LOCAL_RTX"
          and h.get("X-Fallback") == "false" and el < 10.0)
    print("F3 " + ("PASS (preventivo directo, sin intento de conexion)" if ok else "FAIL"))
srv.shutdown()
