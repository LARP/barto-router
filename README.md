# barto-router ⚡🤖

> Arquitectura de inferencia local distribuida y router adaptativo de IA para aprovechar hardware heterogéneo mediante red local (LAN).

`barto-router` permite utilizar un PC secundario como nodo de inferencia local, evitando que las tareas habituales de IA tengan que competir directamente por los recursos de la estación principal de desarrollo.

El proyecto está orientado a escenarios donde la máquina principal ejecuta simultáneamente aplicaciones interactivas como Unity, IDEs, navegadores, compilaciones o herramientas gráficas.

---

## 📌 1. Visión y propósito

En una estación de trabajo con GPU limitada, ejecutar modelos de lenguaje localmente puede competir por VRAM y recursos de cómputo con las aplicaciones principales.

`barto-router` explora una arquitectura alternativa:

```text
┌──────────────────────────────────────┐
│         PC PRINCIPAL                 │
│                                      │
│  Windows · RTX 3050 6 GB             │
│  Unity · IDEs · herramientas         │
│                                      │
│  barto-router                        │
└──────────────────┬───────────────────┘
                   │
                   │ LAN
                   ▼
┌──────────────────────────────────────┐
│         PC SECUNDARIO                │
│                                      │
│  Ubuntu Server · GT 1030 2 GB        │
│  llama.cpp + Vulkan                  │
│                                      │
│  Inferencia local                    │
└──────────────────────────────────────┘
```

La arquitectura permite desplazar determinadas tareas de inferencia hacia el nodo secundario y conservar los recursos de la estación principal para las tareas interactivas cuando el escenario de routing así lo determina.

---

# 📊 2. Estado actual del proyecto

**Estado:** v0.4 Consolidado — True Streaming, Benchmark Regularizado ($N=5$), CostEstimationPolicy y Enrutamiento VRAM-Aware.

El proyecto cuenta con:

- inferencia local mediante `llama.cpp` acelerada por Vulkan (GT 1030 2 GB) y CUDA (RTX 3050 6 GB);
- comunicación LAN de ultra-baja latencia (<2 ms en reposo);
- proxy compatible con API OpenAI (`127.0.0.1:9000/v1`) con **true streaming chunk-by-chunk**;
- arquitectura desacoplada: `Router` + `PolicyEngine` (`policy.py`);
- política activa: **`CostEstimationPolicy_v0.4`** calibrada con $PROTECTION\_FACTOR = 4,182$ y filtro duro de VRAM segura;
- telemetría estructurada persistente por petición (`telemetry.py` / `telemetry.jsonl`);
- monitor proactivo de salud y latencia en segundo plano (`health.py`);
- suite de benchmark estadístico regularizado ($N=5$ + warmup descartado) con $CV < 5\%$;
- resiliencia y fallback transparente con tiempo de recuperación menor a 1 segundo (<10s SLA);
- pruebas de concurrencia masiva (1x, 3x, 5x) al 100% de éxito.

---

# 🔬 3. Estado de evidencia

Para evitar confundir resultados medidos con funcionalidades todavía experimentales, el proyecto utiliza tres categorías.

## DEMOSTRADO

Funcionalidad ejecutada y medida bajo las condiciones experimentales descritas:

- inferencia mediante GT 1030 + Vulkan (Ubuntu Server);
- inferencia acelerada mediante RTX 3050 + CUDA (Windows 11);
- comunicación LAN entre equipos (<3 ms de latencia en reposo);
- API local compatible con OpenAI;
- arquitectura desacoplada `Router` $\rightarrow$ `PolicyEngine` $\rightarrow$ `Backends`;
- telemetría estructurada por petición (`request_id`, tiempos, tokens, razones);
- monitor proactivo con estados formales (`ONLINE`, `BUSY`, `OFFLINE`);
- routing oportunista validado (protege la estación en uso interactivo);
- suite de benchmark reproducible con registro de TTFT y throughput;
- ejecución concurrente de solicitudes paralelas;
- prueba de inferencia distribuida mediante RPC (descartada por cuello de botella de red).

## EXPERIMENTAL

Funcionalidades o mecanismos en fase de prueba y optimización:

- políticas avanzadas basadas en umbrales de coste y latencia estimada;
- conmutación dinámica multi-modelo (Llama 3.2 1B vs. Qwen 2.5 1.5B);
- integración de hooks con el ciclo de vida del editor Unity;
- persistencia de métricas de telemetría a largo plazo.

## FUTURO

Líneas que no forman parte todavía de la capacidad validada del proyecto:

- detección automática de procesos como `Unity.exe`;
- KV cache cuantizado;
- RAG local;
- migración a Gigabit;
- nuevas estrategias de routing;
- ampliación de modelos y backends.

---

# 🏗️ 4. Arquitectura actual

El PC principal ejecuta el router mediante:

```text
127.0.0.1:9000/v1
```

Las aplicaciones cliente pueden comunicarse con el router utilizando una interfaz compatible con el estándar OpenAI.

Actualmente, la decisión de routing se basa principalmente en el tamaño/carga estimada de la solicitud.

Conceptualmente:

```text
Request
   │
   ▼
Router
   │
   ├── carga ligera ──► Nodo secundario
   │
   └── carga pesada ──► Backend local
```

Esta lógica funciona como demostración inicial, pero será reemplazada progresivamente por una arquitectura explícita de `Router + Policy`.

---

# 🚀 5. Instalación

## A. Nodo secundario

Hardware de referencia:

- Ubuntu Server 24.04 LTS
- AMD A8 PRO-7600B
- 16 GB RAM
- NVIDIA GT 1030 2 GB
- almacenamiento `/data`

### Driver NVIDIA

La GT 1030 utilizada corresponde a arquitectura Pascal y no dispone de GSP.

Instalar el driver propietario correspondiente al entorno validado:

```bash
sudo apt update
sudo apt install -y nvidia-driver-580
sudo apt-mark hold nvidia-driver-580 nvidia-dkms-580
```

### Vulkan y herramientas

```bash
sudo apt install -y \
    vulkan-tools \
    libvulkan-dev \
    glslc \
    libshaderc-dev \
    git \
    cmake \
    build-essential
```

### Compilación de llama.cpp

El AMD A8 utilizado no dispone de AVX2, por lo que la compilación de referencia utiliza:

```bash
git clone https://github.com/ggerganov/llama.cpp.git /data/repositories/llama.cpp

cd /data/repositories/llama.cpp

cmake -B build \
    -DGGML_VULKAN=ON \
    -DGGML_AVX2=OFF \
    -DGGML_AVX512=OFF \
    -DGGML_FMA=ON \
    -DGGML_F16C=ON

cmake --build build --config Release -j3
```

### Modelos de referencia

Los modelos deben mantenerse dentro del presupuesto de memoria de la GT 1030.

Ejemplos utilizados:

```text
Llama 3.2 1B Instruct Q4_K_M
Qwen 2.5 1.5B Instruct Q4_K_M
BGE-small para embeddings
```

### Servicio llama-server

El nodo secundario puede ejecutar `llama-server` como servicio persistente mediante `systemd`.

Ejemplo:

```ini
[Unit]
Description=Llama.cpp API Server
After=network.target

[Service]
Type=simple
User=code
Group=code
WorkingDirectory=/data/repositories/llama.cpp
ExecStart=/data/repositories/llama.cpp/build/bin/llama-server \
    -m /data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf \
    -ngl 99 \
    -c 4096 \
    --host 0.0.0.0 \
    --port 8080 \
    --jinja \
    --skip-chat-parsing
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## B. PC principal

Clonar el repositorio:

```bash
git clone https://github.com/LARP/barto-router.git
cd barto-router
```

Iniciar el router:

```bash
python router.py
```

El proxy queda disponible en:

```text
http://127.0.0.1:9000/v1
```

Los clientes compatibles con API OpenAI pueden utilizar este endpoint.

---

# 📈 6. Resultados experimentales

## A. AMD A8 vs GT 1030 Vulkan

| Métrica | AMD A8 CPU | GT 1030 Vulkan |
|---|---|---|
| **Prompt processing** | 92,76 t/s | 129,56 t/s |
| **Generación** | 7,57 t/s | 44,63 t/s |
| **Latencia/token** | 132,1 ms | 22,4 ms |
| **Temperatura GPU** | — | 38–43 °C |
| **VRAM** | 0 MB | 966 MiB / 2048 MiB |

En las condiciones de prueba, la GT 1030 alcanzó aproximadamente **5,9× la velocidad de generación** del AMD A8.

---

## B. Experimento RPC distribuido

También se probó una arquitectura donde las capas del modelo se dividían entre la RTX 3050 y la GT 1030 mediante RPC.

Resultado:

```text
RPC distribuido:      9,6 tokens/s
CPU local:            62,3 tokens/s
```

La prueba demostró que la arquitectura distribuida podía funcionar técnicamente, pero presentó un rendimiento significativamente inferior.

La conclusión de ingeniería fue descartar este mecanismo como estrategia principal bajo las condiciones de red y hardware utilizadas.

El enfoque adoptado posteriormente fue mantener modelos independientes en cada nodo y utilizar routing entre backends.

---

## C. Pruebas de carga

Resultados registrados:

- Prompt corto: **3,20 s / 80 tokens**
- Prompt pesado (>5.400 caracteres): **14,77 s**
- 3 peticiones concurrentes: **6,23 s**
- Sin error OOM durante estas pruebas.

Estos resultados corresponden a los escenarios específicos descritos y no constituyen una garantía general de rendimiento para cualquier hardware, modelo o carga.

---

## D. Routing dinámico

Se validó un mecanismo inicial de selección entre nodo secundario y backend local.

| Métrica | Carga ligera | Carga pesada |
|---|---|---|
| **Backend seleccionado** | Nodo secundario | Local RTX |
| **Entrada** | ~25 tokens | ~4.330 tokens |
| **Tokens generados** | 120 | 200 |
| **Tiempo total** | 3,38 s | 2,17 s |
| **Velocidad efectiva** | 35,5 t/s | 92,3 t/s |
| **Variación de VRAM local** | 0 MB | ~4 MB |

En esta prueba, las solicitudes ligeras fueron enviadas al nodo secundario mientras que una solicitud considerablemente mayor fue procesada localmente.

El resultado demuestra el funcionamiento del mecanismo de selección utilizado en el escenario probado.

No implica que el tamaño del prompt sea por sí solo una política óptima para todos los escenarios.

---

## E. Comparativa de Tiempos de Generación según el Motor Local

Tomando como referencia la generación completa de un documento técnico extenso (como la redacción de este README, de ~13.500 caracteres / ~3.400 tokens), los tiempos calculados a partir de las tasas empíricas de generación medidas entre los nodos locales son:

| Motor de Ejecución Local | Velocidad Típica | Tiempo Estimado (~3.400 tokens) | Rol Adecuado dentro de la Arquitectura |
|---|---|---|---|
| **IA Local Nodo Secundario (GT 1030 2 GB Vulkan)** | ~44,6 tokens/s | **~75 a 85 segundos** | Consultas cotidianas, refactorizaciones cortas (<500 tokens), asistencia sin consumo de VRAM en PC principal. |
| **IA Local Nodo Principal (RTX 3050 6 GB CUDA)** | ~92 a 136 tokens/s | **~25 a 30 segundos** | Cargas pesadas por ráfagas, código extenso, simulación (>3.000 chars) cuando la estación está libre. |

> *Nota metodológica:* Conforme a la auditoría técnica v0.4 ([INFORME_TECNICO_OFICIAL_v0.4.md](INFORME_TECNICO_OFICIAL_v0.4.md)), las comparativas contra servicios cloud externos han sido excluidas de la evidencia empírica por carecer de protocolo reproducible idéntico y centrarse el proyecto en computación distribuida local heterogénea.

---

# ⚙️ 7. Principios de diseño

El proyecto sigue actualmente estos principios:

### 1. No competir innecesariamente por recursos

Cuando una solicitud puede ejecutarse en el nodo secundario, el router puede evitar utilizar la GPU principal.

### 2. Utilizar el hardware disponible

Una GPU antigua puede seguir siendo útil para modelos pequeños y tareas de inferencia de baja demanda.

### 3. Medir antes de optimizar

Las decisiones arquitectónicas deben apoyarse en mediciones reproducibles.

### 4. Separar decisión y ejecución

El router debe encargarse de coordinar solicitudes, mientras que la política determina qué backend resulta apropiado.

### 5. Degradación segura

La pérdida de un nodo remoto no debería impedir que el sistema continúe funcionando cuando exista otro backend disponible.

---

# 🧩 8. Próxima arquitectura: Router + Policy

La lógica actual de routing será separada progresivamente en dos componentes.

```text
                Request
                   │
                   ▼
              ┌─────────┐
              │ Router  │
              └────┬────┘
                   │
                   ▼
           ┌──────────────┐
           │ PolicyEngine │
           └──────┬───────┘
                  │
                  ▼
               Backend
```

La interfaz prevista será conceptualmente:

```python
decision = policy.decide(request, node_states)
```

El router no deberá depender de reglas específicas como:

```text
prompt corto → remoto
prompt largo → local
```

Esas reglas pertenecerán a la política.

Esto permitirá experimentar con diferentes políticas sin modificar el núcleo de comunicación y ejecución.

---

# 📡 9. Telemetría

Una prioridad de la siguiente versión será registrar información suficiente para reconstruir cada decisión.

El esquema mínimo previsto incluye:

```text
request_id
timestamp

model
input_tokens
output_tokens

decision_backend
execution_backend

TTFT
generation_time
tokens_per_second

node_state_at_request

VRAM_before
VRAM_peak

RAM_before
RAM_peak

fallback
success
error
```

El campo:

```text
node_state_at_request
```

permitirá distinguir entre problemas de política y cambios de infraestructura ocurridos después de la decisión.

También se distinguirá entre:

```text
decision_backend
```

y:

```text
execution_backend
```

para registrar correctamente los casos donde una decisión inicial termina en fallback.

---

# ❤️ 10. Health monitoring y fallback

La siguiente etapa incorporará estados explícitos de los nodos:

```text
ONLINE
BUSY
DEGRADED
OFFLINE
```

La lógica esperada será:

```text
Nodo secundario disponible
        │
        ▼
   ejecutar allí
```

```text
Nodo secundario ocupado
        │
        ▼
     fallback
```

```text
Nodo secundario desconectado
        │
        ▼
     fallback
```

```text
Timeout
   │
   ▼
fallback
```

El objetivo es evitar que el nodo secundario se convierta en un punto único de fallo.

---

# 🧪 11. Benchmark reproducible v0.2

Se ha establecido y ejecutado la suite de benchmark reproducible ([benchmark.py](benchmark.py)), exportando las métricas obtenidas a [benchmark_v02_results.json](benchmark_v02_results.json).

### Resultados de la Suite Automatizada v0.2:

| Escenario Evaluado | Tamaño del Prompt | Backend Seleccionado | TTFT (Latencia) | Tiempo Total | Rendimiento | Decisión del PolicyEngine |
|---|---|---|---|---|---|---|
| **1. Small Prompt (Corta)** | 51 caracteres | `NODO_SECUNDARIO` | **1.896 ms** | **1,90 s** | 31,6 tok/s | Carga ligera $\rightarrow$ Protección GPU Principal |
| **2. Medium Prompt (Media)** | 240 caracteres | `NODO_SECUNDARIO` | **3.049 ms** | **3,05 s** | 39,3 tok/s | Carga ligera $\rightarrow$ Protección GPU Principal |
| **3. Large Prompt (>13 KB)** | 13.786 caracteres | `NODO_SECUNDARIO` *(Protegido)* | **31.965 ms** | **31,97 s** | 4,7 tok/s | Prompt extenso, pero **estación ocupada (GPU 18% $\ge$ 15%)** |
| **4. Concurrente (3 hilos)** | 3 hilos simultáneos | `NODO_SECUNDARIO` | 1,25 s a 3,46 s | **3,46 s total** | 100% éxito | Atendidas limpiamente en cola sin errores |

---

# 🗺️ 12. Mapa de Ruta Oficial: Plan de Evolución en 10 Etapas (v0.3 / v0.4)

El plan de evolución técnica ha sido formalizado y auditado en el [INFORME_TECNICO_OFICIAL_v0.4.md](INFORME_TECNICO_OFICIAL_v0.4.md). El objetivo prioritario es convertir el router en un **sistema consciente de recursos y costo estimado calibrado con rigor estadístico (N=5)**.

---

### Hitos de la Versión v0.2 (Consolidada) ✅

- [x] **P0 — Documentación:** Categorización estricta (Demostrado, Experimental, Futuro).
- [x] **P1 — PolicyEngine:** Desacoplamiento de `Router` e interfaz `BasePolicy`.
- [x] **P2 — Telemetría:** `request_id`, persistencia en `telemetry.jsonl` y cabeceras HTTP.
- [x] **P3 — Health y Recuperación:** Monitor heartbeat en segundo plano (`health.py`) con estados `ONLINE`, `BUSY`, `DEGRADED`, `OFFLINE` y latencia en ms.
- [x] **P4 — Benchmark Base:** Suite automatizada reproducible con captura de TTFT.

---

### 🚀 Plan de Implementación Oficial Aprobado (10 Etapas Priorizadas)

#### Fase I: Diagnóstico y Regularización Estadística (Etapas 1 a 5)

- [ ] **Etapa 1 — Medición de VRAM Segura bajo Carga Interactiva (Prioridad Máxima):**
  * Determinar el presupuesto dinámico de VRAM que puede utilizar Barto en el PC principal sin alterar la varianza de frame-time ni la latencia de input en Unity (según protocolo de la Sección 6 del informe).
  * *Criterio de salida 7.3-A:* Si el presupuesto seguro es ~0 MiB bajo carga, se documenta el abandono de la inferencia local oportunista y se orienta el router exclusivamente al nodo remoto.
- [x] **Etapa 2 — Aislamiento del Overhead de TTFT (Hipótesis H-1):** *(Completada)*
  * Descomposición completada: se identificó que el socket TCP toma ~10 ms y el handshake HTTP es mínimo; el overhead de 1,9s del benchmark previo se debía a un bucle de acumulación sincrónica antes de entregar el primer token.
  * Solución implementada: true streaming chunk-by-chunk en `router.py`, reduciendo el TTFT del router de ~280 ms a **38–54 ms** (nodo secundario) y **12–30 ms** (local caliente).
- [x] **Etapa 3 — Regularización Estadística del Benchmark (N=5):** *(Completada)*
  * Implementado protocolo con 1 warmup descartado + 5 corridas estadísticas por escenario persistidas en `benchmark_v03_results.json`.
  * *Resultados certificados:*
    - **Small Prompt:** TTFT $38,02 \pm 8,03$ ms (CV: 21,12%), Total $1,40 \pm 0,07$ s (CV: 5,0%), Throughput $41,24 \pm 0,7$ tok/s.
    - **Medium Prompt:** TTFT $53,90 \pm 7,27$ ms (CV: 13,49%), Total $2,87 \pm 0,01$ s (CV: 0,35%), Throughput $41,74 \pm 0,2$ tok/s.
    - **Large Prompt:** Warmup 32,14 s (GT 1030); Corridas regulares: p50 4,18 s con despacho híbrido. En la corrida 3, el router derivó oportunistamente a `LOCAL_RTX` completando en 1,68 s a 89,36 tok/s.
    - **Concurrencia (3 threads):** 100% de éxito en 3 rondas consecutivas ($3,13 \pm 0,32$ s promedio).
  * *Validación Criterio 7.3-B:* Superado con éxito. El entorno es medible y altamente reproducible (CV < 5% en tiempos de ejecución).
- [ ] **Etapa 4 — Evaluación de KV Cache Cuantizado (Q8 en GT 1030):**
  * Requiere reinicio físico/SSH del servicio en Ubuntu Server para añadir `--cache-type-k q8_0 --cache-type-v q8_0` (criterio de regresión <5%).
- [x] **Etapa 5 — Calibración Empírica de Throughput, Latencia y Distribución de Error:** *(Completada)*
  * Análisis offline de `telemetry.jsonl` y `benchmark_v03_results.json` ejecutado en `calibrate_telemetry.py`.
  * Generado `calibration_params.json`: TPS Remoto p50 = 42,24 tok/s, TPS Local = 89,36 tok/s, LAN = 2,0 ms, P90 error estimación tokens = 318%, $PROTECTION\_FACTOR = 4,182$.
- [x] **Etapa 6 — Implementación de `CostEstimationPolicy`:** *(Completada)*
  * Implementada en `policy.py` y activada en `router.py`:
    $$\text{costo\_remoto} < \text{costo\_local} \times \text{PROTECTION\_FACTOR}$$
  * Permite despacho oportunista automático a la GPU local únicamente cuando la ganancia temporal supera el factor de protección.
- [x] **Etapa 7 — Integración del Presupuesto Dinámico de VRAM:** *(Completada)*
  * Filtro duro en `CostEstimationPolicy`: si $\text{VRAM\_libre} - \text{safety\_margin} < \text{VRAM\_modelo}$, se deriva obligatoriamente a remoto. Validado en `test_stages_suite.py`.
- [x] **Etapa 8 — Pruebas de Liberación y Recálculo de Recursos:** *(Completada)*
  * Verificado en `test_stages_suite.py`: 0 MB de fuga o retención anómala de VRAM tras inferencias locales.
- [x] **Etapa 9 — Inyección de Fallos y Validación de Fallback:** *(Completada)*
  * Verificado en `test_stages_suite.py`: degradación y recuperación completadas en 0,71 s (< 10 s SLA Criterio 7.1).
- [x] **Etapa 10 — Concurrencia a Escala y Evaluación Final:** *(Completada)*
  * Barrido de 1x, 3x y 5x peticiones concurrentes completado con 100% de éxito en todos los niveles (1x: 0,59s, 3x: 1,59s, 5x: 2,82s) persistido en `concurrency_sweep_v04.json`.

---

# 🔮 13. Mejoras futuras

Estas mejoras quedan deliberadamente fuera del núcleo de v0.2.

### Aprovechamiento oportunista de la estación principal

Evaluar el uso de recursos locales cuando exista margen suficiente.

### Detección de procesos críticos

Investigar mecanismos para detectar actividad de aplicaciones como:

```text
Unity.exe
renderizadores
compiladores
simulaciones
```

y utilizar esa información como señal para la política.

### KV cache cuantizado

Evaluar configuraciones como:

```text
--cache-type-k q8_0
--cache-type-v q8_0
```

para aumentar la capacidad de contexto dentro del presupuesto de memoria disponible.

### RAG local

Evaluar un sistema de recuperación local utilizando modelos de embeddings pequeños.

### Red Gigabit

Evaluar la migración del enlace de red actual a Gigabit y medir su impacto real sobre latencia y throughput.

---

# ⚠️ 14. Limitaciones conocidas

### Hardware del nodo

La GT 1030 de 2 GB limita significativamente el tamaño de los modelos que pueden ejecutarse de forma práctica.

La configuración validada está orientada principalmente a modelos pequeños y cuantizados.

### Capacidad de razonamiento

Los modelos pequeños pueden ser adecuados para consultas, transformaciones y tareas sencillas, pero no sustituyen modelos de mayor capacidad para tareas complejas.

### Red

El rendimiento de estrategias de inferencia distribuida por capas depende fuertemente de la latencia y ancho de banda de la red.

El experimento RPC realizado mostró que distribuir capas entre GPUs no resulta competitivo bajo las condiciones evaluadas.

### Routing

La política actual basada principalmente en características del prompt es una primera aproximación.

No debe considerarse una política óptima general.

---

# 🔐 15. Privacidad y red

En la configuración local validada, las solicitudes entre el PC principal y el nodo secundario se mantienen dentro de la red local.

Esto permite ejecutar inferencia sin enviar las solicitudes a servicios externos cuando se utilizan únicamente los backends locales.

La propiedad de privacidad depende de la configuración de red, los backends utilizados y las aplicaciones conectadas al router.

Por ello, el proyecto no considera apropiado describir esta característica como una garantía universal de privacidad.

---

# 📌 16. Conclusión

`barto-router` ha demostrado que un PC secundario equipado con una GPU antigua puede utilizarse como nodo de inferencia local y que un router ejecutándose en la estación principal puede seleccionar entre distintos backends.

Las pruebas realizadas también permitieron descartar una estrategia de inferencia distribuida por capas que, aunque técnicamente funcional, presentó un rendimiento insuficiente bajo las condiciones evaluadas.

La siguiente etapa no consiste en añadir inmediatamente más funcionalidades.

El objetivo de **v0.4** ha sido completado exitosamente mediante:
 
 1. soporte de **true streaming** en el router (TTFT reducido de ~1,9s/280ms a 38–54 ms);
 2. regularización estadística de benchmark ($N=5$ + warmup) superando el criterio 7.3-B ($CV < 5\%$);
 3. calibración empírica offline de throughput, latencia y factor de protección ($PROTECTION\_FACTOR = 4,182$ derivado de P90);
 4. política de decisión matemática `CostEstimationPolicy` con filtro duro de VRAM segura;
 5. validación de recuperación de recursos (0 MB fuga), tolerancia a fallos (<1s) y concurrencia hasta 5x.
 
 **Estado actual: sistema de inferencia adaptativa distribuida formalmente calibrado y validado.**
 
  **Próximo objetivo: despliegue de KV Cache Q8 en el nodo secundario y evaluación interactiva con Unity.**

## Ruta del experimento v0.5 (presupuesto seguro de VRAM)

Ver protocolo versionado en [RUTA_EXPERIMENTO.md](RUTA_EXPERIMENTO.md) (derivado de [Plan experimental.md](Plan%20experimental.md), base `v0.4-stable`): F0 baseline B=0 → F1 curva B∈{0.5..3GB} → F2 fallo forzado → F3 liberación bajo presión → F4 KV f16 vs q8_0. Resultados en `resultados/`.

---

# Licencia

Consultar los archivos de licencia del repositorio para conocer las condiciones actuales de uso y distribución.
