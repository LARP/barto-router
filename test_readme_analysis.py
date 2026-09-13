import time
import json
import urllib.request
import subprocess
import threading
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

README_URL = "https://raw.githubusercontent.com/LARP/barto-router/main/README.md"
LOCAL_ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"
NODO_DIRECT_URL = "http://192.168.100.105:8080/v1/chat/completions"

def get_gpu_metrics():
    """Consulta las métricas actuales de la GPU local RTX 3050."""
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

def main():
    print("=" * 70)
    print("   TEST DE CARGA CON README.MD — IA LOCAL Y MONITOR DE GPU")
    print("=" * 70)
    
    # 1. Descargar README
    print("\n[1] Descargando README desde GitHub...")
    req = urllib.request.Request(README_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        readme_text = r.read().decode("utf-8")
    
    chars = len(readme_text)
    print(f"    -> Descargado con éxito: {chars} caracteres ({chars / 1024:.2f} KB)")

    # 2. Métricas iniciales de la GPU local (RTX 3050)
    print("\n[2] Estado inicial de la GPU Local (PC Principal - RTX 3050):")
    init_gpu = get_gpu_metrics()
    print(f"    - Carga de GPU:     {init_gpu.get('util_percent')}%")
    print(f"    - VRAM en uso:      {init_gpu.get('mem_used_mb')} MB / Libre: {init_gpu.get('mem_free_mb')} MB")
    print(f"    - Temperatura:      {init_gpu.get('temp_c')} °C")
    print(f"    - Consumo Energía:  {init_gpu.get('power_w')} W")

    # 3. Determinar endpoint (Router o Nodo Directo)
    endpoint = NODO_DIRECT_URL
    target_label = "Nodo Remoto GT 1030 (192.168.100.105:8080)"
    try:
        urllib.request.urlopen("http://127.0.0.1:9000/health", timeout=0.2)
        endpoint = LOCAL_ROUTER_URL
        target_label = "barto-router (127.0.0.1:9000)"
    except Exception:
        pass

    print(f"\n[3] Destino de la petición: {target_label}")
    print(f"    Endpoint URL: {endpoint}")

    # 4. Monitor concurrente de GPU mientras se ejecuta la inferencia
    stop_monitor = False
    gpu_samples = []

    def monitor_worker():
        while not stop_monitor:
            m = get_gpu_metrics()
            if "error" not in m:
                gpu_samples.append(m)
            time.sleep(0.2)

    t_thread = threading.Thread(target=monitor_worker)
    t_thread.daemon = True
    t_thread.start()

    # 5. Enviar petición a la IA local
    prompt = (
        f"A continuación tienes el README completo de un proyecto de arquitectura de IA.\n\n"
        f"```markdown\n{readme_text}\n```\n\n"
        f"Por favor responde en español:\n"
        f"1. ¿Cuál es el propósito principal del proyecto?\n"
        f"2. ¿Qué hardware utiliza cada equipo?\n"
        f"3. Resumen breve en 2 líneas de los resultados obtenidos."
    )

    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente técnico analista de documentación y arquitectura de software."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    post_req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )

    print("\n[4] Enviando prompt masivo a la IA local y monitoreando en tiempo real...")
    t0 = time.time()
    try:
        with urllib.request.urlopen(post_req, timeout=120) as response:
            resp_bytes = response.read()
            total_time = time.time() - t0
            quien_responde = response.headers.get("X-Processed-By", target_label)
            res_json = json.loads(resp_bytes.decode("utf-8"))
    except Exception as e:
        stop_monitor = True
        print(f"    [!] Error en la petición: {e}")
        return

    stop_monitor = True
    t_thread.join(timeout=1)

    # 6. Analizar respuesta y métricas
    content = res_json["choices"][0]["message"]["content"]
    usage = res_json.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    tps = completion_tokens / total_time if total_time > 0 else 0

    print("\n" + "=" * 70)
    print("                     RESULTADOS DEL ANÁLISIS")
    print("=" * 70)
    print(f"  ● Quién Responde:       {quien_responde}")
    print(f"  ● Tiempo Total:         {total_time:.2f} segundos")
    print(f"  ● Tokens de Entrada:    {prompt_tokens} tokens (~{chars} caracteres)")
    print(f"  ● Tokens Generados:     {completion_tokens} tokens")
    print(f"  ● Velocidad Efectiva:   {tps:.1f} tokens/s (incluyendo procesamiento del prompt)")
    
    # Análisis de muestras de GPU local durante la prueba
    if gpu_samples:
        max_util = max(s["util_percent"] for s in gpu_samples)
        avg_util = sum(s["util_percent"] for s in gpu_samples) / len(gpu_samples)
        max_vram = max(s["mem_used_mb"] for s in gpu_samples)
        min_vram = min(s["mem_used_mb"] for s in gpu_samples)
        max_pwr = max(s["power_w"] for s in gpu_samples)
        avg_temp = sum(s["temp_c"] for s in gpu_samples) / len(gpu_samples)

        print("\n  ● Impacto en GPU Local (PC Principal - RTX 3050):")
        print(f"    - Muestras tomadas:   {len(gpu_samples)} (intervalo 200 ms)")
        print(f"    - Carga de GPU:       Promedio {avg_util:.1f}% | Pico máximo: {max_util}%")
        print(f"    - Variación VRAM:     {min_vram} MB -> {max_vram} MB (Diferencia: {max_vram - min_vram} MB)")
        print(f"    - Temperatura prom:   {avg_temp:.1f} °C")
        print(f"    - Consumo Pico:       {max_pwr:.1f} W")
        if max_util <= 5 and (max_vram - min_vram) < 50:
            print("    -> CONCLUSIÓN GPU: AISLAMIENTO 100% CONFIRMADO. Cero impacto en la estación de trabajo.")
    
    print("\n" + "-" * 70)
    print("RESPUESTA GENERADA POR LA IA:")
    print("-" * 70)
    print(content)
    print("=" * 70)

if __name__ == "__main__":
    main()
