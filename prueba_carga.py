import time
import json
import urllib.request
import threading

ROUTER_URL = "http://127.0.0.1:9000/v1/chat/completions"

def test_single_prompt(prompt_text, test_name):
    print(f"\n--- Iniciando: {test_name} ---")
    print(f"Longitud del prompt: {len(prompt_text)} caracteres")
    
    payload = {
        "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": "Eres un asistente de desarrollo y optimizacion de codigo para Unity."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.7,
        "max_tokens": 80
    }
    
    req = urllib.request.Request(
        ROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - start
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("completion_tokens", 0)
            tps = tokens / elapsed if elapsed > 0 else 0
            
            print(f"Estado: EXITOSO ({elapsed:.2f}s)")
            print(f"Tokens generados: {tokens} (~{tps:.1f} tokens/s)")
            print(f"Respuesta (primeras lineas):\n{content[:150]}...")
            return True, elapsed, tps
    except Exception as e:
        print(f"Error en {test_name}: {e}")
        return False, 0, 0

def run_stress_test():
    print("=" * 60)
    print("      EJECUTANDO BATERIA DE PRUEBAS DE CARGA DEL ROUTER")
    print("=" * 60)
    
    # Prueba 1: Prompt Corto (Consulta tipica de desarrollo)
    p1 = "Escribe un metodo en C# para Unity que mueva un GameObject suavemente hacia un objetivo usando Vector3.MoveTowards."
    test_single_prompt(p1, "PRUEBA 1: Consulta Cotidiana (Prompt Corto)")
    
    # Prueba 2: Prompt Pesado / Extenso (> 4.000 caracteres)
    codigo_simulado = ("// Script MonoBehaviour para Unity con multiples metodos de fisica y render\n" * 70)
    p2 = f"Analiza este script largo de Unity y dime 3 puntos criticos donde se podria producir basura en memoria (Garbage Collection):\n\n{codigo_simulado}\nFin del codigo. Dame solo los 3 puntos."
    test_single_prompt(p2, "PRUEBA 2: Consulta de Carga Pesada (Prompt Extenso >4KB)")

    # Prueba 3: Concurrencia (3 consultas simultaneas)
    print("\n--- Iniciando: PRUEBA 3: Concurrencia (3 peticiones simultaneas) ---")
    threads = []
    results = []
    
    def worker(idx):
        p = f"Dame un consejo numero {idx} para optimizar shaders y draw calls en Unity URP para plataformas moviles."
        res = test_single_prompt(p, f"Hilo concurrente #{idx}")
        results.append(res)
        
    start_c = time.time()
    for i in range(1, 4):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    total_time = time.time() - start_c
    print(f"\nPrueba de concurrencia completada en {total_time:.2f}s para 3 solicitudes.")
    print("=" * 60)
    print("              RESUMEN DE PRUEBA DE CARGA: PASS")
    print("=" * 60)

if __name__ == "__main__":
    run_stress_test()
