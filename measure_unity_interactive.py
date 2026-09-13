"""
measure_unity_interactive.py — Protocolo de Medición de VRAM Segura (Etapa 1)
Mide el impacto de Unity.exe en Modo Play sobre la GPU local (RTX 3050 6GB)
y calibra el safety_margin para el enrutador adaptativo.
"""

import time
import subprocess
import statistics
import sys
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def get_gpu_sample():
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"
        ]
        out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
        util, mem_used, mem_free, temp, pwr = [x.strip() for x in out.split(",")]
        return {
            "util_pct": int(util),
            "mem_used_mb": int(mem_used),
            "mem_free_mb": int(mem_free),
            "temp_c": int(temp),
            "power_w": float(pwr)
        }
    except Exception as e:
        return None

def check_unity_process():
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-Process -Name 'Unity' -ErrorAction SilentlyContinue | Select-Object -First 1 -Property Id, ProcessName, WorkingSet64, PM"
        ]
        out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
        return out
    except Exception:
        return None

def run_sampling(duration_sec: int = 15, interval_sec: float = 0.5):
    print("=" * 65)
    print(" PROTOCOLO DE MEDICIÓN DE VRAM INTERACTIVA (UNITY EN PLAY)")
    print("=" * 65)
    
    unity_info = check_unity_process()
    if unity_info and "Unity" in unity_info:
        print("[INFO] Proceso Unity detectado:")
        for line in unity_info.splitlines():
            if line.strip():
                print(f"   {line.strip()}")
    else:
        print("[AVISO] No se detectó Unity en ejecución automática.")
        
    print(f"\n[1] Muestreando GPU a {1/interval_sec:.1f} Hz durante {duration_sec} segundos...")
    print("    (Por favor, interactúa o mueve la cámara en Unity durante la toma de datos)")
    
    samples = []
    t_end = time.time() + duration_sec
    step = 0
    while time.time() < t_end:
        s = get_gpu_sample()
        if s:
            samples.append(s)
            step += 1
            if step % 4 == 0:
                print(f"  [{step*interval_sec:4.1f}s] GPU: {s['util_pct']:2d}% | VRAM Usada: {s['mem_used_mb']:4d} MB | VRAM Libre: {s['mem_free_mb']:4d} MB | Temp: {s['temp_c']}°C")
        time.sleep(interval_sec)
        
    if not samples:
        print("[ERROR] No se pudieron capturar muestras.")
        return
        
    vram_free = [s["mem_free_mb"] for s in samples]
    vram_used = [s["mem_used_mb"] for s in samples]
    gpu_util = [s["util_pct"] for s in samples]
    
    mean_free = statistics.mean(vram_free)
    min_free = min(vram_free)
    max_used = max(vram_used)
    mean_util = statistics.mean(gpu_util)
    max_util = max(gpu_util)
    
    # Percentil 5 de VRAM libre (peor caso conservador)
    vram_free_sorted = sorted(vram_free)
    p05_idx = max(0, int(len(vram_free_sorted) * 0.05))
    p05_free = vram_free_sorted[p05_idx]
    
    print("\n" + "-" * 65)
    print(" RESULTADOS DEL ANÁLISIS DE CARGA DE UNITY EN PLAY")
    print("-" * 65)
    print(f"  Muestras capturadas:          {len(samples)}")
    print(f"  Carga GPU (Media / Pico):      {mean_util:.1f}% / {max_util}%")
    print(f"  VRAM Usada (Pico máximo):      {max_used} MB")
    print(f"  VRAM Libre (Media):            {mean_free:.1f} MB")
    print(f"  VRAM Libre Mínima Observable:  {min_free} MB")
    print(f"  VRAM Libre P05 (Conservadora): {p05_free} MB")
    
    # Cálculo del Presupuesto y Safety Margin recomendado
    # Regla: Margen de seguridad = (Pico de VRAM observada - Base) + 500MB buffer de textura dinámica
    vram_jitter = max_used - min(vram_used)
    recommended_safety_margin = max(1500, vram_jitter * 2 + 1000)
    safe_budget_for_inference = max(0, min_free - recommended_safety_margin)
    
    print("\n--- Calibración para Barto Router ---")
    print(f"  Varianza / Jitter de VRAM:    ±{vram_jitter} MB")
    print(f"  Safety Margin Recomendado:    {recommended_safety_margin} MB")
    print(f"  Presupuesto Seguro Inferencia: {safe_budget_for_inference} MB")
    
    # Verificación con modelo local Llama 3.2 1B (requiere ~1200-1400 MB)
    model_req = 1200
    can_run_local = safe_budget_for_inference >= model_req
    print(f"\n  ¿Puede la estación ejecutar modelo local (1200 MB) de forma segura?")
    if can_run_local:
        print(f"  -> SÍ: Hay {safe_budget_for_inference} MB seguros disponibles.")
    else:
        print(f"  -> NO (o solo en reposo): Presupuesto seguro ({safe_budget_for_inference} MB) < {model_req} MB.")
        print(f"     La política enviará peticiones al NODO_SECUNDARIO para blindar Unity.")
        
    res_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples_count": len(samples),
        "gpu_util_mean": round(mean_util, 1),
        "gpu_util_max": max_util,
        "vram_used_max_mb": max_used,
        "vram_free_min_mb": min_free,
        "vram_free_p05_mb": p05_free,
        "vram_jitter_mb": vram_jitter,
        "recommended_safety_margin_mb": recommended_safety_margin,
        "safe_budget_mb": safe_budget_for_inference,
        "can_run_local_safely": can_run_local
    }
    
    with open("unity_interactive_measurement.json", "w", encoding="utf-8") as f:
        json.dump(res_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nGuardado en unity_interactive_measurement.json")

if __name__ == "__main__":
    run_sampling(duration_sec=15, interval_sec=0.5)
