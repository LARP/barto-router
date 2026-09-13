"""
diagnose_ttft.py — Protocolo de Aislamiento de TTFT (Hipótesis H-1)
Fase I - Etapa 2: Aislamiento del Overhead de TTFT en Barto Router

Objetivo:
Descomponer y aislar las fuentes de latencia en TTFT (Time-To-First-Token)
comparando:
1. TCP Handshake / Conexión (DNS + Connect)
2. HTTP Keep-Alive (Reutilización de socket vs Nueva conexión TCP por petición)
3. Directo a Secundario (192.168.100.105:8080) vs Router Proxy (127.0.0.1:9000) vs Local (127.0.0.1:8081)
4. Cold Start vs Warm Slot en llama-server (procesamiento KV cache y prompt eval)
"""

import time
import json
import socket
import statistics
import requests

PROMPT_SHORT = "Hola, responde brevemente: ¿cuál es la capital de Francia?"

TARGETS = {
    "DIRECT_SECUNDARIO": "http://192.168.100.105:8080/v1/chat/completions",
    "ROUTER_PROXY": "http://127.0.0.1:9000/v1/chat/completions",
    "DIRECT_LOCAL": "http://127.0.0.1:8081/v1/chat/completions"
}

def measure_raw_tcp(host, port, repetitions=5):
    """Mide latencia de establecimiento de conexión TCP pura (SYN -> SYN-ACK -> ACK)."""
    latencies = []
    for _ in range(repetitions):
        t0 = time.perf_counter()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect((host, port))
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
        except Exception as e:
            latencies.append(None)
        finally:
            s.close()
        time.sleep(0.05)
    valid = [l for l in latencies if l is not None]
    return {
        "mean_ms": round(statistics.mean(valid), 2) if valid else None,
        "min_ms": round(min(valid), 2) if valid else None,
        "max_ms": round(max(valid), 2) if valid else None
    }

def measure_inference_streaming(url, payload, use_session=True, repetitions=3):
    """
    Mide TTFT (Time To First Token) exacto y tiempo total utilizando Server-Sent Events (stream=True).
    Registra:
    - connect_overhead: tiempo hasta recibir el primer chunk HTTP con contenido de token.
    - total_time: tiempo hasta fin del stream.
    - tokens_received: conteo de chunks/tokens.
    """
    results = []
    
    session = requests.Session() if use_session else None

    for i in range(repetitions):
        req_client = session if use_session else requests
        
        t_start = time.perf_counter()
        t_first_token = None
        token_count = 0
        
        try:
            response = req_client.post(
                url,
                json=payload,
                stream=True,
                timeout=30.0
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode('utf-8', errors='replace')
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                if t_first_token is None:
                                    t_first_token = time.perf_counter()
                                token_count += 1
                    except Exception:
                        pass
                        
            t_end = time.perf_counter()
            
            ttft_ms = round((t_first_token - t_start) * 1000.0, 2) if t_first_token else None
            total_ms = round((t_end - t_start) * 1000.0, 2)
            
            results.append({
                "iteration": i + 1,
                "ttft_ms": ttft_ms,
                "total_ms": total_ms,
                "tokens": token_count,
                "keep_alive": use_session,
                "headers": dict(response.headers)
            })
        except Exception as e:
            results.append({
                "iteration": i + 1,
                "error": str(e)
            })
            
        time.sleep(0.1)

    if not use_session and session:
        session.close()

    return results

def run_diagnostics():
    print("=================================================================")
    print(" BARTO ROUTER — ETAPA 2: PROTOCOLO DE AISLAMIENTO TTFT (H-1)    ")
    print("=================================================================\n")

    # 1. Medición de capa de red TCP pura
    print("[1/3] Evaluando Handshake TCP puro (Capa 4)...")
    tcp_secundario = measure_raw_tcp("192.168.100.105", 8080)
    tcp_router = measure_raw_tcp("127.0.0.1", 9000)
    tcp_local = measure_raw_tcp("127.0.0.1", 8081)

    print(f"  - TCP Secundario (192.168.100.105:8080): {tcp_secundario['mean_ms']} ms (min: {tcp_secundario['min_ms']}, max: {tcp_secundario['max_ms']})")
    print(f"  - TCP Router Local (127.0.0.1:9000):     {tcp_router['mean_ms']} ms (min: {tcp_router['min_ms']}, max: {tcp_router['max_ms']})")
    print(f"  - TCP Local Backend (127.0.0.1:8081):    {tcp_local['mean_ms']} ms (min: {tcp_local['min_ms']}, max: {tcp_local['max_ms']})")

    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": PROMPT_SHORT}],
        "max_tokens": 60,
        "temperature": 0.2,
        "stream": True
    }

    report = {
        "tcp_raw": {
            "secundario": tcp_secundario,
            "router": tcp_router,
            "local": tcp_local
        },
        "experiments": {}
    }

    # 2. Pruebas de Inferencia: Nueva conexión vs Keep-Alive
    # Experimento A: Directo a Secundario (Sin Keep-Alive)
    print("\n[2/3] Evaluando Directo a Secundario:")
    print("  a) Conexión fresca por petición (Sin Keep-Alive)...")
    res_sec_nokeep = measure_inference_streaming(TARGETS["DIRECT_SECUNDARIO"], payload, use_session=False, repetitions=3)
    print(f"     Iteraciones TTFT: {[r.get('ttft_ms') for r in res_sec_nokeep]}")

    print("  b) Conexión persistente reutilizada (Keep-Alive)...")
    res_sec_keep = measure_inference_streaming(TARGETS["DIRECT_SECUNDARIO"], payload, use_session=True, repetitions=3)
    print(f"     Iteraciones TTFT: {[r.get('ttft_ms') for r in res_sec_keep]}")

    # Experimento B: A través del Router (Proxy)
    print("\n[3/3] Evaluando a través de Barto Router:")
    print("  a) Router con conexión fresca...")
    res_rout_nokeep = measure_inference_streaming(TARGETS["ROUTER_PROXY"], payload, use_session=False, repetitions=3)
    print(f"     Iteraciones TTFT: {[r.get('ttft_ms') for r in res_rout_nokeep]}")

    print("  b) Router con conexión persistente (Keep-Alive)...")
    res_rout_keep = measure_inference_streaming(TARGETS["ROUTER_PROXY"], payload, use_session=True, repetitions=3)
    print(f"     Iteraciones TTFT: {[r.get('ttft_ms') for r in res_rout_keep]}")

    # Experimento C: Local Directo (RTX 3050)
    print("\n[Control] Evaluando Local Directo (RTX 3050):")
    res_loc_keep = measure_inference_streaming(TARGETS["DIRECT_LOCAL"], payload, use_session=True, repetitions=3)
    print(f"     Iteraciones TTFT: {[r.get('ttft_ms') for r in res_loc_keep]}")

    report["experiments"]["direct_secundario_no_keepalive"] = res_sec_nokeep
    report["experiments"]["direct_secundario_keepalive"] = res_sec_keep
    report["experiments"]["router_proxy_no_keepalive"] = res_rout_nokeep
    report["experiments"]["router_proxy_keepalive"] = res_rout_keep
    report["experiments"]["direct_local_keepalive"] = res_loc_keep

    with open("diagnose_ttft_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\n[OK] Diagnostico completado. Resultados guardados en diagnose_ttft_results.json")

if __name__ == "__main__":
    run_diagnostics()
