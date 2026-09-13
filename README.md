# barto-router ⚡🤖

> **Arquitectura de Inferencia Local Distribuida y Router Adaptativo de IA.**  
> Maximiza el aprovechamiento de hardware reciclado (NVIDIA GT 1030 2GB + Ubuntu Server) como nodo auxiliar de IA por red local (LAN), protegiendo al 100% la VRAM y potencia de la estación principal de desarrollo (RTX 3050 / Unity3D / IDEs).

---

## 📌 1. Visión y Propósito del Proyecto

En entornos de desarrollo interactivo (como el desarrollo de videojuegos con **Unity3D**, compilaciones o renderizado), correr modelos de lenguaje locales en la misma GPU compite directamente por la VRAM y provoca caídas severas de fotogramas, congelamiento del editor o cierres inesperados por falta de memoria gráfica.

**barto-router** soluciona este dilema convirtiendo un PC secundario de bajo costo en un **nodo esclavo de IA autónomo**:
1. **El PC Secundario (Nodo Linux):** Absorbe todo el cómputo de inferencia (40–45 tokens/s) mediante `llama.cpp` y aceleración Vulkan sobre una GT 1030 de 2 GB.
2. **El PC Principal (Windows):** Ejecuta un **Router Adaptativo en tiempo real** que intercepta las peticiones de desarrollo (desde OpenCode, Cursor, scripts o navegadores) y las despacha de forma invisible por la red local sin consumir un solo megabyte de la RTX 3050 principal.

---

## 🏗️ 2. Arquitectura del Sistema

```
 ┌───────────────────────────────────────────────────────────┐
 │               PC PRINCIPAL (Estación de Trabajo)          │
 │                 Windows 11 · i7 · RTX 3050 6GB            │
 │                                                           │
 │   • Unity3D / Blender / IDEs (100% de VRAM reservada)     │
 │   • OpenCode / Navegador Web                              │
 │   • barto-router (Proxy Inteligente en 127.0.0.1:9000)     │
 └─────────────────────────────┬─────────────────────────────┘
                               │
                               │ LAN Gigabit / FastEthernet (< 4ms latencia)
                               │ Puerto 8080 (API) / 50052 (RPC) / 22 (SSH)
                               ▼
 ┌───────────────────────────────────────────────────────────┐
 │               PC SECUNDARIO (Nodo Auxiliar de IA)         │
 │           Ubuntu Server 24.04 LTS · AMD A8 · GT 1030 2GB  │
 │                                                           │
 │   • llama-server daemon (arranque automático con systemd) │
 │   • Backend Vulkan 1.3 optimizado para arquitectura Pascal│
 │   • Almacenamiento masivo /data (300 GB ext4)             │
 │   • Modelos: Llama 3.2 1B (45 t/s) · Qwen 2.5 1.5B (35 t/s│
 └───────────────────────────────────────────────────────────┘
```

---

## 🚀 3. Guía Paso a Paso de Instalación

### A. Preparación del Nodo Secundario (Ubuntu Server 24.04 LTS)
1. **Instalación de Sistema:**
   - Instalar Ubuntu Server 24.04 LTS en el disco destino (`ext4`), preservando el arranque dual UEFI/GRUB.
   - Montar el almacenamiento secundario en `/data` mediante UUID en `/etc/fstab`.
2. **Driver Gráfico Propietario (NVIDIA GT 1030 Pascal):**
   > *Regla crítica:* La GT 1030 (chip GP108) carece de procesador GSP. No utilizar drivers `-open`.
   ```bash
   sudo apt update
   sudo apt install -y nvidia-driver-580
   sudo apt-mark hold nvidia-driver-580 nvidia-dkms-580
   ```
3. **Instalación del Stack Vulkan y Herramientas de Compilación:**
   ```bash
   sudo apt install -y vulkan-tools libvulkan-dev glslc libshaderc-dev git cmake build-essential
   ```
4. **Compilación de `llama.cpp` a la medida de la CPU (AMD A8 sin AVX2):**
   ```bash
   git clone https://github.com/ggerganov/llama.cpp.git /data/repositories/llama.cpp
   cd /data/repositories/llama.cpp
   cmake -B build -DGGML_VULKAN=ON -DGGML_AVX2=OFF -DGGML_AVX512=OFF -DGGML_FMA=ON -DGGML_F16C=ON
   cmake --build build --config Release -j3
   ```
5. **Descarga de Modelos Prevalidados (dentro del presupuesto de 2 GB VRAM):**
   ```bash
   mkdir -p /data/models
   # Primario Rápido: Llama 3.2 1B (~770 MB)
   curl -L -o /data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf 'https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf'
   # Modelo de Código/Razonamiento: Qwen 2.5 1.5B (~1.05 GB)
   curl -L -o /data/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf'
   # Embeddings para RAG: BGE-Small (~36 MB)
   curl -L -o /data/models/bge-small-en-v1.5-q8_0.gguf 'https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/main/bge-small-en-v1.5-q8_0.gguf'
   ```
6. **Configuración del Servicio Persistente (`systemd`):**
   Crear `/etc/systemd/system/llama-server.service`:
   ```ini
   [Unit]
   Description=Llama.cpp API Server (GT 1030 Vulkan)
   After=network.target

   [Service]
   Type=simple
   User=code
   Group=code
   WorkingDirectory=/data/repositories/llama.cpp
   ExecStart=/data/repositories/llama.cpp/build/bin/llama-server -m /data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf -ngl 99 -c 4096 --host 0.0.0.0 --port 8080 --jinja --skip-chat-parsing
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   Habilitar e iniciar:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now llama-server.service
   ```

---

### B. Configuración de barto-router en el PC Principal (Windows)
1. Clonar este repositorio en tu PC de trabajo.
2. Iniciar el router proxy inteligente:
   ```powershell
   python router.py
   ```
3. El router queda escuchando en `http://127.0.0.1:9000/v1` compatible con el estándar OpenAI.
4. **Integración con OpenCode:** Configurar `opencode.jsonc` apuntando a `http://127.0.0.1:9000/v1`.

---

## 📊 4. Pruebas Realizadas y Métricas Empíricas

### A. Rendimiento en el Nodo Secundario (AMD A8 vs. GT 1030 Vulkan)

| Prueba | CPU AMD A8 (Sin GPU) | GT 1030 2GB (Vulkan) | Impacto / Mejora |
|---|---|---|---|
| **Procesamiento de Prompt** | 92.76 t/s | **129.56 t/s** | **+39.7% más rápido** |
| **Generación de Tokens** | 7.57 t/s | **44.63 t/s** | **+489.5% (5.9× más rápido)** 🚀 |
| **Latencia por Token** | 132.1 ms | **22.4 ms** | **6× menos tiempo de espera** |
| **Temperatura de la GPU** | N/A | **38°C – 43°C** | Muy fría y estable bajo carga |
| **VRAM Utilizada** | 0 MB | **966 MiB / 2048 MiB** | **> 1 GB libre de margen** |

### B. Experimento RPC Distribuido (Dividir capas entre RTX 3050 y GT 1030 por LAN)

Se ejecutó una prueba dividiendo capas por TCP (`ggml-rpc-server`):
- **Resultado Técnico:** PASS. Ambas GPUs colaboraron y generaron texto coherente.
- **Resultado Práctico:** **9.6 tokens/s** (RPC LAN) frente a **62.3 tokens/s** (CPU Local).
- **Conclusión de Ingeniería:** La latencia de la red FastEthernet (95 Mbps) y la diferencia de velocidad entre ambas tarjetas genera cuello de botella. **El modo desacoplado por API independiente (barto-router) es 4.5× superior al modo distribuido por capas.**

### C. Prueba de Carga y Concurrencia con barto-router

- **Prompt Corto:** 3.20 segundos (80 tokens).
- **Prompt Pesado (>5.400 caracteres de código):** 14.77 segundos sin error OOM ni degradación.
- **Concurrencia (3 peticiones en paralelo):** Atendidas limpiamente en 6.23 segundos en total.
- **Impacto en PC Principal (Unity3D):** **0.0% de uso de VRAM y CPU.**

---

## ⚖️ 5. Análisis de Viabilidad: ¿Es Beneficioso?

### ✅ Ventajas Confirmadas:
1. **Aislamiento Total de Recursos:** Unity3D y los proyectos gráficos en el PC principal disponen del 100% de la RTX 3050 en todo momento.
2. **Cero Costo en Tokens Cloud:** Respuestas ilimitadas para tareas repetitivas de desarrollo (refactorizaciones, consultas de sintaxis C#, explicaciones de errores).
3. **Reutilización de Hardware:** Una GPU de entrada de 2017 (GT 1030) entrega una velocidad de lectura de IA superior a la velocidad de lectura humana (45 t/s).
4. **Privacidad Absoluta:** Ningún fragmento de código ni consulta sale a internet; todo el tráfico se restringe a la subred local (`192.168.100.0/24`).

### ⚠️ Limitaciones Identificadas:
1. **Límite de Parámetros del Modelo:** El nodo está restringido a modelos de 1B a 3B parámetros con cuantizaciones Q4 para no exceder los 2 GB de VRAM.
2. **Capacidad de Razonamiento:** Para arquitecturas de software complejas o refactorizaciones masivas de múltiples archivos, se requiere recurrir al PC principal o a modelos de mayor escala.

---

## 🔮 6. Próximas Mejoras Propuestas

- [ ] **Detección Automática de Proceso Unity (Play Mode):** Integrar hook que sondee `Unity.exe` y fuerce desvío al nodo si el editor está en ejecución activa.
- [ ] **KV Cache Cuantizado a `q8_0`:** Activar `--cache-type-k q8_0 --cache-type-v q8_0` para duplicar la ventana de contexto a 8.192 tokens con el mismo consumo de VRAM.
- [ ] **Canal RAG Local en el Nodo:** Aprovechar el modelo `bge-small-en-v1.5` descargado en `/data/models` para indexar la documentación de la API de Unity localmente en SQLite/ChromaDB.
- [ ] **Red Gigabit (1000 Mbps):** Migrar el enlace LAN a switch Gigabit para habilitar transferencias masivas de contexto en microsegundos.
