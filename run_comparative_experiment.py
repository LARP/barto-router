import sys
import os
import time
import json
import urllib.request
import subprocess
import threading

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"

def get_gpu_metrics():
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

def execute_test(test_name, prompt_text, max_tokens=150):
    print("=" * 70)
    print(f"   EJECUTANDO: {test_name}")
    print("=" * 70)
    print(f"Longitud del Prompt: {len(prompt_text)} caracteres (~{len(prompt_text)/3.2:.0f} tokens)")
    
    stop_sampling = False
    samples = []
    
    def sampler():
        while not stop_sampling:
            m = get_gpu_metrics()
            if "error" not in m:
                samples.append(m)
            time.sleep(0.1)

    t = threading.Thread(target=sampler)
    t.daemon = True
    t.start()

    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente de arquitectura de software y optimización."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens
    }

    req = urllib.request.Request(
        ROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            elapsed = time.time() - t0
            nodo = resp.headers.get("X-Processed-By", "Desconocido")
            data = json.loads(raw)
    except Exception as e:
        stop_sampling = True
        print(f"[!] Error ejecutando {test_name}: {e}")
        return None

    stop_sampling = True
    t.join(timeout=1)

    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    tps = completion_tokens / elapsed if elapsed > 0 else 0
    content = data["choices"][0]["message"]["content"]

    gpu_max_util = max(s["util_percent"] for s in samples) if samples else 0
    gpu_avg_util = sum(s["util_percent"] for s in samples) / len(samples) if samples else 0
    gpu_max_vram = max(s["mem_used_mb"] for s in samples) if samples else 0
    gpu_min_vram = min(s["mem_used_mb"] for s in samples) if samples else 0
    gpu_max_pwr = max(s["power_w"] for s in samples) if samples else 0

    res = {
        "test_name": test_name,
        "nodo": nodo,
        "elapsed_seconds": elapsed,
        "prompt_chars": len(prompt_text),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_second": tps,
        "gpu_max_util": gpu_max_util,
        "gpu_avg_util": gpu_avg_util,
        "gpu_vram_delta_mb": gpu_max_vram - gpu_min_vram,
        "gpu_max_vram_mb": gpu_max_vram,
        "gpu_max_pwr_w": gpu_max_pwr,
        "response_preview": content[:180]
    }

    print(f"\n[RESULTADO] Nodo Destino:       {nodo}")
    print(f"            Tiempo Total:       {elapsed:.2f} s")
    print(f"            Tokens Generados:   {completion_tokens} ({tps:.1f} tok/s)")
    print(f"            Pico GPU Local:     {gpu_max_util}% (VRAM delta: {gpu_max_vram - gpu_min_vram} MB)")
    print(f"            Pico Energía Local: {gpu_max_pwr:.1f} W")
    print(f"            Respuesta:          {content[:140]}...\n")
    return res

def main():
    print("INICIANDO EXPERIMENTO COMPARATIVO DE ENRUTAMIENTO DINAMICO")
    print("Router en: http://127.0.0.1:9000/v1")
    time.sleep(1)

    # 1. Test Ligero (< 3000 chars) -> Nodo Secundario (GT 1030)
    p_light = "Explica en 3 viñetas qué es el Garbage Collection en C# y cómo evitarlo en Unity."
    res_light = execute_test("TEST 1: Carga Ligera (Prompt Corto)", p_light, max_tokens=120)

    # 2. Test Pesado (> 3000 chars) -> Nodo Principal (RTX 3050)
    codigo_extenso = """
    using System;
    using System.Collections.Generic;
    using UnityEngine;

    public class BigSimulationManager : MonoBehaviour
    {
        private List<Vector3> entityPositions = new List<Vector3>();
        private float[] velocities = new float[50000];

        void Start()
        {
            for (int i = 0; i < 50000; i++)
            {
                entityPositions.Add(new Vector3(i * 0.1f, Mathf.Sin(i), Mathf.Cos(i)));
                velocities[i] = UnityEngine.Random.Range(1.0f, 15.0f);
            }
        }

        void Update()
        {
            // Simulación intensiva en CPU
            for (int i = 0; i < entityPositions.Count; i++)
            {
                Vector3 pos = entityPositions[i];
                pos.x += velocities[i] * Time.deltaTime;
                pos.y = Mathf.Sin(pos.x);
                entityPositions[i] = pos;
            }
        }
    }
    """ * 15 # ~12.000 caracteres

    p_heavy = (
        "Analiza detalladamente este script de simulación masiva en Unity. "
        "Enumera 4 optimizaciones de alto rendimiento usando Unity DOTS, Jobs System y Burst Compiler:\n\n"
        + codigo_extenso
    )
    
    res_heavy = execute_test("TEST 2: Carga Pesada (Prompt Extenso >12 KB)", p_heavy, max_tokens=200)

    # Guardar resultados en JSON para el informe
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "light_test": res_light,
        "heavy_test": res_heavy
    }

    with open("D:\\opencode\\test\\resultados_experimento_carga.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Resultados guardados en: D:\\opencode\\test\\resultados_experimento_carga.json")

if __name__ == "__main__":
    main()
