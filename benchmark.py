"""
benchmark.py — Suite de Benchmark Reproducible v0.3
Fase I - Etapa 3: Regularización Estadística (N=5) de Barto Router

Metodología:
- 1 corrida de Warmup (descartada de métricas para aislar cold start de buffers/GPU/socket)
- N=5 corridas de medición estadística
- Métricas calculadas:
    * Media y Desviación Estándar (mean +/- std)
    * Mediana (p50)
    * Percentil 95 (p95)
    * Coeficiente de Variación (CV% = std / mean * 100) -> Control de criterio de abandono 7.3-B (< 25%)
- Persistencia estructurada en benchmark_v03_results.json
"""

import time
import json
import urllib.request
import subprocess
import threading
import statistics
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:9000/health"

def get_gpu_telemetry():
    """Captura métricas de la GPU local RTX 3050 vía nvidia-smi."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        util, mem_used, mem_free, temp, pwr = [x.strip() for x in res.stdout.strip().split(",")]
        return {
            "util_percent": int(util),
            "mem_used_mb": int(mem_used),
            "mem_free_mb": int(mem_free),
            "temp_c": int(temp),
            "power_w": float(pwr)
        }
    except Exception as e:
        return {"error": str(e)}

def execute_single_stream_request(prompt_text: str, max_tokens: int = 100):
    """Ejecuta una única petición streaming y mide con precisión tiempos exactos."""
    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente de optimización de software y desarrollo."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": True
    }

    req = urllib.request.Request(
        ROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    t0 = time.time()
    ttft = None
    tokens_received = 0
    full_text = []

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            headers = dict(resp.headers)
            req_id = headers.get("X-Request-ID", "N/A")
            dec_backend = headers.get("X-Decision-Backend", "N/A")
            exec_backend = headers.get("X-Execution-Backend", "N/A")
            fallback = headers.get("X-Fallback", "false")

            for line in resp:
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str.startswith("data: ") and line_str != "data: [DONE]":
                    if ttft is None:
                        ttft = (time.time() - t0) * 1000.0  # ms
                    try:
                        chunk = json.loads(line_str[6:])
                        content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if content:
                            tokens_received += 1
                            full_text.append(content)
                    except json.JSONDecodeError:
                        continue

            total_time = time.time() - t0
            tps = tokens_received / total_time if total_time > 0 else 0

            return {
                "success": True,
                "request_id": req_id,
                "decision_backend": dec_backend,
                "execution_backend": exec_backend,
                "fallback": fallback,
                "prompt_chars": len(prompt_text),
                "tokens_generated": tokens_received,
                "ttft_ms": round(ttft, 2) if ttft else None,
                "total_time_s": round(total_time, 3),
                "tokens_per_second": round(tps, 2)
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "prompt_chars": len(prompt_text)
        }

def calc_percentile(data, p):
    """Calcula percentil p (0..100) sobre lista ordenada."""
    if not data:
        return None
    k = (len(data) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c < len(data):
        return data[f] + (k - f) * (data[c] - data[f])
    return data[f]

def run_regularized_benchmark(scenario_name: str, prompt_text: str, max_tokens: int = 100, n_runs: int = 5):
    """
    Ejecuta el protocolo de la Etapa 3:
    1 Warmup (descartado) + N mediciones formales con análisis estadístico.
    """
    print(f"\n========================================================")
    print(f">> Escenario: {scenario_name}")
    print(f"   Longitud: {len(prompt_text)} caracteres | Generación max: {max_tokens} tokens")
    print(f"========================================================")

    # 1. Warmup
    print("   [Warmup] Enviando corrida de calentamiento (no computada en estadísticas)...", end="", flush=True)
    w_start = time.time()
    w_res = execute_single_stream_request(prompt_text, max_tokens)
    w_elapsed = time.time() - w_start
    if w_res.get("success"):
        print(f" OK ({w_elapsed:.2f}s | TTFT: {w_res.get('ttft_ms')}ms | {w_res.get('execution_backend')})")
    else:
        print(f" FALLÓ: {w_res.get('error')}")

    time.sleep(0.3)

    # 2. Corridas N=5
    runs = []
    ttfts = []
    totals = []
    tpss = []
    backends_used = []

    for i in range(1, n_runs + 1):
        print(f"   [Run {i}/{n_runs}] Ejecutando...", end="", flush=True)
        res = execute_single_stream_request(prompt_text, max_tokens)
        if res.get("success"):
            runs.append(res)
            ttfts.append(res["ttft_ms"])
            totals.append(res["total_time_s"])
            tpss.append(res["tokens_per_second"])
            backends_used.append(res["execution_backend"])
            print(f" OK -> TTFT: {res['ttft_ms']:.1f}ms | Total: {res['total_time_s']:.2f}s | {res['tokens_per_second']:.1f} t/s [{res['execution_backend']}]")
        else:
            print(f" ERROR: {res.get('error')}")
        time.sleep(0.2)

    # 3. Análisis Estadístico
    def compute_stats(series):
        if not series:
            return {}
        s_sorted = sorted(series)
        mean_val = round(statistics.mean(series), 2)
        stdev_val = round(statistics.stdev(series), 2) if len(series) > 1 else 0.0
        cv_pct = round((stdev_val / mean_val * 100.0), 2) if mean_val > 0 else 0.0
        return {
            "mean": mean_val,
            "stdev": stdev_val,
            "p50": round(statistics.median(series), 2),
            "p95": round(calc_percentile(s_sorted, 95), 2),
            "min": round(min(series), 2),
            "max": round(max(series), 2),
            "cv_percent": cv_pct
        }

    ttft_stats = compute_stats(ttfts)
    total_stats = compute_stats(totals)
    tps_stats = compute_stats(tpss)

    print(f"\n   [Estadísticas N={len(runs)}]")
    print(f"   • TTFT:  {ttft_stats.get('mean')} ± {ttft_stats.get('stdev')} ms | p50: {ttft_stats.get('p50')} ms | p95: {ttft_stats.get('p95')} ms (CV: {ttft_stats.get('cv_percent')}%)")
    print(f"   • Total: {total_stats.get('mean')} ± {total_stats.get('stdev')} s  | p50: {total_stats.get('p50')} s  | p95: {total_stats.get('p95')} s  (CV: {total_stats.get('cv_percent')}%)")
    print(f"   • Vel:   {tps_stats.get('mean')} ± {tps_stats.get('stdev')} t/s | p50: {tps_stats.get('p50')} t/s | p95: {tps_stats.get('p95')} t/s")

    return {
        "scenario_name": scenario_name,
        "prompt_chars": len(prompt_text),
        "target_max_tokens": max_tokens,
        "warmup_run": w_res,
        "runs_n": len(runs),
        "execution_backends": list(set(backends_used)),
        "metrics": {
            "ttft_ms": ttft_stats,
            "total_time_s": total_stats,
            "tokens_per_second": tps_stats
        },
        "raw_runs": runs
    }

def run_concurrent_regularized(concurrency: int = 3, n_rounds: int = 3):
    print(f"\n========================================================")
    print(f">> Suite Concurrencia: {concurrency} peticiones concurrentes ({n_rounds} rondas)")
    print(f"========================================================")

    rounds = []
    round_totals = []

    for r in range(1, n_rounds + 1):
        print(f"   [Ronda {r}/{n_rounds}] Lanzando {concurrency} hilos simultáneos...", end="", flush=True)
        results = []
        threads = []

        def worker(idx):
            p = f"Dame un consejo breve #{idx} para optimizar código en C#."
            res = execute_single_stream_request(p, max_tokens=40)
            results.append(res)

        t0 = time.time()
        for i in range(1, concurrency + 1):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=120)

        total_r = time.time() - t0
        round_totals.append(total_r)
        successes = sum(1 for res in results if res.get("success"))
        print(f" OK: {successes}/{concurrency} exitosas en {total_r:.2f}s")
        rounds.append({
            "round": r,
            "elapsed_s": round(total_r, 2),
            "success_rate": f"{successes}/{concurrency}",
            "items": results
        })
        time.sleep(0.3)

    return {
        "scenario_name": f"Concurrent_{concurrency}",
        "concurrency_level": concurrency,
        "rounds_n": n_rounds,
        "mean_elapsed_s": round(statistics.mean(round_totals), 2),
        "stdev_elapsed_s": round(statistics.stdev(round_totals), 2) if len(round_totals) > 1 else 0.0,
        "rounds": rounds
    }

def main():
    print("*" * 72)
    print("   BARTO-ROUTER — BENCHMARK REGULARIZADO v0.3 (N=5 + Warmup)")
    print("   Cumplimiento de Etapa 3 y Criterios Estadísticos (Informe Oficial v0.4)")
    print("*" * 72)

    # 1. Comprobar salud inicial
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as h_resp:
            health_data = json.loads(h_resp.read().decode())
            print("\n[FASE 0] Salud del Router:")
            print(f"   Router Status: {health_data.get('status')}")
            print(f"   Política: {health_data.get('policy')}")
            for k, v in health_data.get("backends", {}).items():
                print(f"   - [{k}]: {v.get('status')} ({v.get('latency_ms')} ms) @ {v.get('url')}")
    except Exception as e:
        print(f"[!] Error conectando a router: {e}")
        return

    init_gpu = get_gpu_telemetry()
    print(f"\n[GPU Local Inicial] Carga: {init_gpu.get('util_percent')}% | VRAM libre: {init_gpu.get('mem_free_mb')} MB | Temp: {init_gpu.get('temp_c')} °C")

    all_results = {
        "benchmark_version": "v0.3_regularized_N5",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "methodology": "1 Warmup descartada + N=5 mediciones por escenario",
        "health_baseline": health_data,
        "gpu_initial": init_gpu,
        "scenarios": []
    }

    # Escenario 1: Small Prompt (<100 chars)
    p_small = "Explica en una frase qué es un GameObject en Unity."
    res_s1 = run_regularized_benchmark("1. Small Prompt (Consulta Corta)", p_small, max_tokens=60, n_runs=5)
    all_results["scenarios"].append(res_s1)

    # Escenario 2: Medium Prompt (~1.200 chars)
    p_medium = (
        "Analiza las diferencias entre Update, FixedUpdate y LateUpdate en Unity. "
        "Detalla el uso de Time.deltaTime vs Time.fixedDeltaTime, y da un ejemplo de código en C# para cada caso. "
        "Explica cuándo usar cada uno en sistemas de físicas y cámaras."
    )
    res_s2 = run_regularized_benchmark("2. Medium Prompt (Contexto Medio)", p_medium, max_tokens=120, n_runs=5)
    all_results["scenarios"].append(res_s2)

    # Escenario 3: Large Prompt (>10.000 chars)
    codigo_extenso = (
        "// Script de renderizado procedural y cálculo de mallas complejas\n"
        "public class ProceduralMeshGenerator : MonoBehaviour {\n"
        "    public int resolution = 256;\n"
        "    private Vector3[] vertices;\n"
        "    private int[] triangles;\n"
        "    void Generate() {\n"
        "        // Loop masivo de cálculo geométrico y normalizado\n"
        "    }\n"
        "}\n"
    ) * 45  # ~11.000 caracteres
    p_large = (
        "Analiza el siguiente código extenso y sugiere 3 técnicas de optimización para memoria y cache coherency:\n\n"
        + codigo_extenso
    )
    res_s3 = run_regularized_benchmark("3. Large Prompt (>10 KB Código)", p_large, max_tokens=150, n_runs=5)
    all_results["scenarios"].append(res_s3)

    # Escenario 4: Concurrencia
    res_s4 = run_concurrent_regularized(concurrency=3, n_rounds=3)
    all_results["scenarios"].append(res_s4)

    # Muestreo GPU Final
    final_gpu = get_gpu_telemetry()
    all_results["gpu_final"] = final_gpu

    # Guardar resultados en JSON
    output_path = "D:\\opencode\\test\\benchmark_v03_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 76)
    print("                    RESUMEN BENCHMARK REGULARIZADO v0.3 (N=5)")
    print("=" * 76)
    for sc in all_results["scenarios"]:
        if "metrics" in sc:
            m = sc["metrics"]
            backends = ", ".join(sc.get("execution_backends", []))
            print(f"  • {sc['scenario_name']:<32} | {backends:<15}")
            print(f"    - TTFT:  {m['ttft_ms']['mean']} ± {m['ttft_ms']['stdev']} ms (p50: {m['ttft_ms']['p50']} ms, p95: {m['ttft_ms']['p95']} ms, CV: {m['ttft_ms']['cv_percent']}%)")
            print(f"    - Total: {m['total_time_s']['mean']} ± {m['total_time_s']['stdev']} s  (p50: {m['total_time_s']['p50']} s,  p95: {m['total_time_s']['p95']} s)")
            print(f"    - Vel:   {m['tokens_per_second']['mean']} ± {m['tokens_per_second']['stdev']} t/s")
        elif "concurrency_level" in sc:
            print(f"  • {sc['scenario_name']:<32} | Concurrencia {sc['concurrency_level']}x | Tiempo promedio ronda: {sc['mean_elapsed_s']} ± {sc['stdev_elapsed_s']} s")

    print(f"\n[GPU Final] Carga: {final_gpu.get('util_percent')}% | VRAM libre: {final_gpu.get('mem_free_mb')} MB | Temp: {final_gpu.get('temp_c')} °C")
    print(f"Reporte estadístico formal exportado a: {output_path}")
    print("=" * 76)

if __name__ == "__main__":
    main()
