"""
benchmark_kv_q8.py — Evaluación rigurosa de Etapa 4: KV Cache Cuantizado Q8_0
Evalúa throughput y latencia en llama-server (GT 1030 Vulkan) con --cache-type-k q8_0 --cache-type-v q8_0
Metodología:
- 1 warmup run descartado
- N=5 corridas de medición
- Criterio de aceptación: Regresión de TPS <= 5.0% respecto al baseline v0.3
"""

import time
import json
import urllib.request
import statistics
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NODE_URL = "http://192.168.100.105:8080/v1/chat/completions"

def run_query(prompt: str, max_tokens: int = 60):
    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente de optimización de software."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": True
    }
    
    req = urllib.request.Request(
        NODE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    t0 = time.time()
    ttft = None
    tokens = 0
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data: "):
                continue
            data_content = line_str[6:].strip()
            if data_content == "[DONE]":
                break
            try:
                chunk = json.loads(data_content)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    if ttft is None:
                        ttft = time.time() - t0
                    tokens += 1
            except Exception:
                pass
                
    total_time = time.time() - t0
    gen_time = (total_time - ttft) if ttft else total_time
    tps = tokens / gen_time if gen_time > 0 else 0
    
    return {
        "ttft_ms": round((ttft or 0) * 1000, 2),
        "total_time_s": round(total_time, 3),
        "tokens": tokens,
        "tps": round(tps, 2)
    }

def evaluate_scenario(name: str, prompt: str, max_tokens: int, baseline_tps: float):
    print(f"\n=======================================================")
    print(f"Evaluando: {name} (N=5 + 1 Warmup)")
    print(f"=======================================================")
    
    # 1. Warmup
    print("  [Warmup] Ejecutando corrida de calentamiento...")
    w = run_query(prompt, max_tokens)
    print(f"  [Warmup] TTFT: {w['ttft_ms']} ms | Tokens: {w['tokens']} | TPS: {w['tps']} t/s (descartada)")
    
    # N=5 runs
    runs = []
    for i in range(1, 6):
        time.sleep(0.5)
        res = run_query(prompt, max_tokens)
        runs.append(res)
        print(f"  Run #{i}: TTFT={res['ttft_ms']} ms | Gen={res['total_time_s']}s | Tokens={res['tokens']} | TPS={res['tps']} t/s")
        
    tps_list = [r["tps"] for r in runs]
    ttft_list = [r["ttft_ms"] for r in runs]
    
    mean_tps = statistics.mean(tps_list)
    stdev_tps = statistics.stdev(tps_list) if len(tps_list) > 1 else 0
    p50_tps = statistics.median(tps_list)
    cv_tps = (stdev_tps / mean_tps) * 100 if mean_tps > 0 else 0
    
    mean_ttft = statistics.mean(ttft_list)
    
    regression = ((baseline_tps - mean_tps) / baseline_tps) * 100
    
    print("\n--- Resultados Estadísticos ---")
    print(f"  Baseline TPS (v0.3 sin cuantizar): {baseline_tps:.2f} t/s")
    print(f"  Nuevo TPS medio (Q8_0):            {mean_tps:.2f} ± {stdev_tps:.2f} t/s (p50: {p50_tps:.2f})")
    print(f"  CV TPS:                             {cv_tps:.2f}%")
    print(f"  TTFT medio:                         {mean_ttft:.2f} ms")
    print(f"  Variación vs Baseline:              {-regression:+.2f}%")
    
    passed = regression <= 5.0
    status_str = "APROBADO (ADOPTAR)" if passed else "RECHAZADO (REGRESIÓN > 5%)"
    print(f"  Criterio de Etapa 4 (<= 5% regresión): [{status_str}]")
    
    return {
        "name": name,
        "baseline_tps": baseline_tps,
        "mean_tps": round(mean_tps, 2),
        "stdev_tps": round(stdev_tps, 2),
        "p50_tps": round(p50_tps, 2),
        "cv_tps": round(cv_tps, 2),
        "mean_ttft_ms": round(mean_ttft, 2),
        "regression_pct": round(regression, 2),
        "passed": passed,
        "runs": runs
    }

if __name__ == "__main__":
    # Baseline Small Prompt en v0.3 fue 41.24 t/s
    prompt_small = "¿Qué es una corrutina y cómo optimiza la memoria?"
    res_small = evaluate_scenario("Small Prompt (51 caracteres)", prompt_small, 60, 41.24)
    
    prompt_med = "¿Podrías darme 3 consejos de rendimiento para optimizar shaders y texturas en GPUs de gama baja?"
    # En v0.3 Medium prompt fue ~39.3 t/s
    res_med = evaluate_scenario("Medium Prompt (100 caracteres)", prompt_med, 80, 39.30)
    
    with open("benchmark_kv_q8_results.json", "w", encoding="utf-8") as f:
        json.dump({"small": res_small, "medium": res_med}, f, indent=2, ensure_ascii=False)
    print("\nResultados persistidos en benchmark_kv_q8_results.json")
