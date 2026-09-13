import sys
import os
import time
import json
import urllib.request
import subprocess

def print_header(title):
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70)

def analyze_local_gpu_nvidia_smi():
    print("\n[1] ANÁLISIS DE HARDWARE GPU LOCAL (NVIDIA-SMI)")
    print("-" * 70)
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free,memory.used,temperature.gpu,power.draw,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        lines = res.stdout.strip().split("\n")
        for idx, line in enumerate(lines):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 8:
                name, driver, mem_total, mem_free, mem_used, temp, pwr, util = parts[:8]
                print(f"  GPU #{idx}: {name}")
                print(f"  Driver Version:      {driver}")
                print(f"  VRAM Total:          {mem_total} MB ({float(mem_total)/1024:.2f} GB)")
                print(f"  VRAM Usada / Libre:  {mem_used} MB / {mem_free} MB")
                print(f"  Temperatura GPU:     {temp} °C")
                print(f"  Consumo de Energía:  {pwr} W")
                print(f"  Carga GPU:           {util} %")
    except Exception as e:
        print(f"  [!] Error consultando nvidia-smi: {e}")

def analyze_local_gpu_pytorch():
    print("\n[2] ANÁLISIS DE ENTORNO CUDA & RENDIMIENTO (PYTORCH)")
    print("-" * 70)
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        print(f"  PyTorch Version:     {torch.__version__}")
        print(f"  CUDA Disponible:     {'SÍ' if cuda_ok else 'NO'}")
        if not cuda_ok:
            return
        
        device_count = torch.cuda.device_count()
        print(f"  Dispositivos CUDA:   {device_count}")
        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            print(f"\n  -- Dispositivo [{i}]: {props.name} --")
            print(f"     Compute Capability: {props.major}.{props.minor}")
            print(f"     Multiprocesadores:  {props.multi_processor_count}")
            print(f"     Memoria Global:     {props.total_memory / (1024**3):.2f} GB")
        
        # Test de Rendimiento de Cómputo (FP32 & FP16 GEMM)
        print("\n  >> Ejecutando Benchmark Rápido de Cómputo (GEMM)...")
        device = torch.device("cuda:0")
        size = 4096
        
        # FP32 Test
        a_fp32 = torch.randn(size, size, device=device, dtype=torch.float32)
        b_fp32 = torch.randn(size, size, device=device, dtype=torch.float32)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        iters = 50
        for _ in range(iters):
            _ = torch.matmul(a_fp32, b_fp32)
        torch.cuda.synchronize()
        elapsed_fp32 = time.perf_counter() - t0
        ops_per_iter = 2 * (size ** 3)
        tflops_fp32 = (ops_per_iter * iters) / (elapsed_fp32 * 1e12)
        print(f"     Rendimiento FP32 (GEMM 4096): {tflops_fp32:.2f} TFLOPS ({elapsed_fp32/iters*1000:.2f} ms/op)")
        
        # FP16 Tensor Core Test
        a_fp16 = a_fp32.half()
        b_fp16 = b_fp32.half()
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = torch.matmul(a_fp16, b_fp16)
        torch.cuda.synchronize()
        elapsed_fp16 = time.perf_counter() - t0
        tflops_fp16 = (ops_per_iter * iters) / (elapsed_fp16 * 1e12)
        print(f"     Rendimiento FP16 (Tensor Core): {tflops_fp16:.2f} TFLOPS ({elapsed_fp16/iters*1000:.2f} ms/op)")
        
        # Test de Ancho de Banda de Memoria H2D / D2H
        print("\n  >> Evaluando Ancho de Banda PCIe (Host <-> Device)...")
        bytes_to_copy = 256 * 1024 * 1024 # 256 MB
        host_tensor = torch.empty(bytes_to_copy // 4, dtype=torch.float32, pin_memory=True)
        
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        dev_tensor = host_tensor.to(device, non_blocking=True)
        torch.cuda.synchronize()
        h2d_time = time.perf_counter() - t0
        h2d_bw = (bytes_to_copy / (1024**3)) / h2d_time
        print(f"     Ancho de Banda H2D (Host -> GPU): {h2d_bw:.2f} GB/s")
        
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = dev_tensor.to("cpu", non_blocking=True)
        torch.cuda.synchronize()
        d2h_time = time.perf_counter() - t0
        d2h_bw = (bytes_to_copy / (1024**3)) / d2h_time
        print(f"     Ancho de Banda D2H (GPU -> Host): {d2h_bw:.2f} GB/s")

    except ImportError:
        print("  [!] PyTorch no está instalado en este entorno Python.")
    except Exception as e:
        print(f"  [!] Error en análisis PyTorch: {e}")

def analyze_remote_gpu_node():
    print("\n[3] ANÁLISIS DE ESTADO NODO REMOTO GPU (Ubuntu Server - GT 1030)")
    print("-" * 70)
    node_url = "http://192.168.100.105:8080"
    print(f"  Comprobando servicio llama-server en {node_url}...")
    
    # 1. Health check
    try:
        req = urllib.request.Request(f"{node_url}/health", headers={"User-Agent": "analisis_gpu"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            print(f"  Estado del Servicio: ONLINE (HTTP {status}) - {body.strip()}")
    except Exception as e:
        print(f"  [!] No se pudo conectar con /health: {e}")
    
    # 2. Inferencia y rendimiento de tokens
    try:
        payload = {
            "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "messages": [
                {"role": "system", "content": "You are a speed test assistant."},
                {"role": "user", "content": "Provide a 25-word summary of GPU computing."}
            ],
            "max_tokens": 40,
            "temperature": 0.2
        }
        req = urllib.request.Request(
            f"{node_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            usage = data.get("usage", {})
            tokens = usage.get("completion_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            tps = tokens / elapsed if elapsed > 0 else 0
            
            print(f"  Modelo Activo:       {data.get('model', 'N/A')}")
            print(f"  Latencia Inferencia: {elapsed:.2f} s")
            print(f"  Tokens Generados:    {tokens} tokens")
            print(f"  Velocidad Efectiva:  {tps:.1f} tokens/s")
            print(f"  Tokens de Prompt:    {prompt_tokens}")
    except Exception as e:
        print(f"  [!] Error probando inferencia en nodo remoto: {e}")

def main():
    print_header("REPORTE COMPLETO DE ANÁLISIS GPU Y CAPACIDADES DE INFERENCIA")
    analyze_local_gpu_nvidia_smi()
    analyze_local_gpu_pytorch()
    analyze_remote_gpu_node()
    print_header("FIN DEL REPORTE DE ANÁLISIS")

if __name__ == "__main__":
    main()
