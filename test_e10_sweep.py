"""E10 ampliada: barrido 1/3/5/10/20 con p50/p95 y backpressure. Contra router real :9000."""
import json, time, threading, urllib.request, statistics

ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"

def one(idx, out):
    p = {"model": "local", "messages": [{"role": "user", "content": f"E10 hilo #{idx}: di ok."}],
         "max_tokens": 15, "stream": False}
    t0 = time.time()
    try:
        req = urllib.request.Request(ROUTER_URL, data=json.dumps(p).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            h = dict(resp.headers)
            resp.read()
            out.append({"ok": resp.status == 200, "lat": time.time() - t0,
                        "exec": h.get("X-Execution-Backend"), "fb": h.get("X-Fallback")})
    except Exception as e:
        out.append({"ok": False, "lat": time.time() - t0, "err": str(e)[:100]})

summary = {}
for conc in [1, 3, 5, 10, 20]:
    results, threads = [], []
    t0 = time.time()
    for i in range(conc):
        th = threading.Thread(target=one, args=(i, results))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    tot = time.time() - t0
    lats = sorted(r["lat"] for r in results)
    ok = sum(1 for r in results if r["ok"])
    summary[conc] = {
        "elapsed_s": round(tot, 2),
        "success_rate": f"{ok}/{conc}",
        "lat_p50_s": round(statistics.median(lats), 2),
        "lat_p95_s": round(lats[min(len(lats) - 1, int(len(lats) * 0.95))], 2),
        "lat_max_s": round(max(lats), 2),
    }
    print(f"Nivel {conc}x: {ok}/{conc} en {tot:.2f}s | p50={summary[conc]['lat_p50_s']}s p95={summary[conc]['lat_p95_s']}s max={summary[conc]['lat_max_s']}s", flush=True)

with open("concurrency_sweep_v04.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
print("OK exportado a concurrency_sweep_v04.json")
