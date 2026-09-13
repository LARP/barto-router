import time
import json
import urllib.request
import subprocess
import threading
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:9000/health"

def get_gpu_telemetry():
    """Captura métricas rápidas de la GPU local RTX 3050."""
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

def run_stream_benchmark(prompt_text: str, max_tokens: int = 100, test_name: str = "Test"):
    """
    Ejecuta una petición en modo streaming contra el router para medir
    con precisión: TTFT, tiempo total, tokens generados y velocidad tok/s.
    """
    print(f"\n>> Ejecutando: {test_name}")
    print(f"   Longitud del prompt: {len(prompt_text)} caracteres")
    
    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente de desarrollo y optimización de software."},
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
                        ttft = (time.time() - t0) * 1000.0  # en ms
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

            print(f"   [OK] Backend: {exec_backend} | ID: {req_id} | Fallback: {fallback}")
            print(f"   Métricas: TTFT = {ttft:.1f}ms | Total = {total_time:.2f}s | Tokens = {tokens_received} (~{tps:.1f} tok/s)")

            return {
                "test_name": test_name,
                "success": True,
                "request_id": req_id,
                "decision_backend": dec_backend,
                "execution_backend": exec_backend,
                "fallback": fallback,
                "prompt_chars": len(prompt_text),
                "tokens_generated": tokens_received,
                "ttft_ms": round(ttft, 1) if ttft else None,
                "total_time_s": round(total_time, 2),
                "tokens_per_second": round(tps, 1)
            }
    except Exception as e:
        print(f"   [FAIL] Error en {test_name}: {e}")
        return {
            "test_name": test_name,
            "success": False,
            "error": str(e)
        }

def run_concurrent_test(concurrency: int = 3):
    print(f"\n>> Ejecutando: Suite Concurrencia ({concurrency} peticiones en paralelo)")
    results = []
    threads = []

    def worker(idx):
        p = f"Dame un consejo breve #{idx} para optimizar código en C#."
        res = run_stream_benchmark(p, max_tokens=40, test_name=f"Concurrente #{idx}")
        results.append(res)

    t0 = time.time()
    for i in range(1, concurrency + 1):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=120)

    total_time = time.time() - t0
    success_count = sum(1 for r in results if r.get("success"))
    print(f"   Resumen Concurrencia: {success_count}/{concurrency} exitosas en {total_time:.2f}s")
    return {
        "test_name": f"Concurrent_{concurrency}",
        "total_elapsed_s": round(total_time, 2),
        "success_rate": f"{success_count}/{concurrency}",
        "items": results
    }

def main():
    print("=" * 70)
    print("   SUITE DE BENCHMARK REPRODUCIBLE v0.2 — BARTO-ROUTER")
    print("=" * 70)

    # 1. Comprobar salud inicial del Router
    print("\n[FASE 0] Comprobando salud inicial del Router y Backends...")
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as h_resp:
            health_data = json.loads(h_resp.read().decode())
            print(f"   Router Status: {health_data.get('status')}")
            print(f"   Política Activa: {health_data.get('policy')}")
            for k, v in health_data.get("backends", {}).items():
                print(f"   - [{k}]: {v.get('status')} ({v.get('latency_ms')} ms) @ {v.get('url')}")
    except Exception as e:
        print(f"[!] No se pudo conectar al router en {HEALTH_URL}: {e}")
        print("Asegúrate de que 'python router.py' esté en ejecución.")
        return

    # Muestreo inicial de GPU local
    init_gpu = get_gpu_telemetry()
    print(f"\n[GPU Local Inicial] Carga: {init_gpu.get('util_percent')}% | VRAM usada: {init_gpu.get('mem_used_mb')} MB | Temp: {init_gpu.get('temp_c')} °C")

    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "health_baseline": health_data,
        "gpu_initial": init_gpu,
        "suites": []
    }

    # Suite 1: Small Prompt (< 100 caracteres) -> Debería ir a NODO_SECUNDARIO
    p_small = "Explica en una frase qué es un GameObject en Unity."
    res_small = run_stream_benchmark(p_small, max_tokens=60, test_name="1. Small Prompt (Consulta Corta)")
    all_results["suites"].append(res_small)

    # Suite 2: Medium Prompt (~1.200 caracteres) -> Debería ir a NODO_SECUNDARIO
    p_medium = (
        "Analiza las diferencias entre Update, FixedUpdate y LateUpdate en Unity. "
        "Detalla el uso de Time.deltaTime vs Time.fixedDeltaTime, y da un ejemplo de código en C# para cada caso. "
        "Explica cuándo usar cada uno en sistemas de físicas y cámaras."
    )
    res_medium = run_stream_benchmark(p_medium, max_tokens=120, test_name="2. Medium Prompt (Contexto Medio)")
    all_results["suites"].append(res_medium)

    # Suite 3: Large Prompt (> 10.000 caracteres) -> Debería ir a LOCAL_RTX
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
    res_large = run_stream_benchmark(p_large, max_tokens=150, test_name="3. Large Prompt (>10 KB Código)")
    all_results["suites"].append(res_large)

    # Suite 4: Concurrencia
    res_conc = run_concurrent_test(concurrency=3)
    all_results["suites"].append(res_conc)

    # Muestreo final de GPU local
    final_gpu = get_gpu_telemetry()
    all_results["gpu_final"] = final_gpu

    # Guardar reporte JSON
    output_path = "D:\\opencode\\test\\benchmark_v02_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("                    RESUMEN DE LA SUITE v0.2")
    print("=" * 70)
    for s in all_results["suites"]:
        if "tokens_per_second" in s:
            print(f"  • {s['test_name']:<35} | Backend: {s.get('execution_backend'):<15} | TTFT: {s.get('ttft_ms')}ms | Vel: {s.get('tokens_per_second')} t/s")
        elif "success_rate" in s:
            print(f"  • {s['test_name']:<35} | Éxito: {s.get('success_rate')} | Tiempo total: {s.get('total_elapsed_s')}s")
    
    print(f"\n[GPU Final] Carga: {final_gpu.get('util_percent')}% | VRAM usada: {final_gpu.get('mem_used_mb')} MB | Temp: {final_gpu.get('temp_c')} °C")
    print(f"Reporte detallado exportado a: {output_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
