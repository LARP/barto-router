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

**Estado:** v0.2 Consolidado — Router instrumentado, modular y basado en políticas.

El proyecto cuenta con:

- inferencia local mediante `llama.cpp`;
- aceleración Vulkan en una NVIDIA GT 1030;
- aceleración CUDA en una NVIDIA RTX 3050 Laptop;
- comunicación LAN transparente entre PC principal y nodo secundario;
- proxy compatible con API OpenAI (`127.0.0.1:9000/v1`);
- arquitectura desacoplada: `Router` + `PolicyEngine` (`policy.py`);
- telemetría estructurada persistente por petición (`telemetry.py` / `telemetry.jsonl`);
- monitor proactivo de salud y latencia en segundo plano (`health.py`);
- suite de benchmark reproducible (`benchmark.py`);
- routing oportunista (protección de la estación de trabajo y ráfagas en GPU local);
- pruebas de carga, concurrencia y tolerancia a fallos.

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

## E. Comparativa de Tiempos de Generación según el Motor de Ejecución

Tomando como referencia la generación completa de un documento técnico extenso (como la redacción de este README, de ~13.500 caracteres / ~3.400 tokens), los tiempos calculados a partir de las tasas empíricas de generación medidas son:

| Motor de Ejecución | Velocidad Típica | Tiempo Estimado (~3.400 tokens) | Rol Adecuado dentro de la Arquitectura |
|---|---|---|---|
| **IA Local Nodo Secundario (GT 1030 2 GB Vulkan)** | ~44,6 tokens/s | **~75 a 85 segundos** | Consultas cotidianas, refactorizaciones cortas (<500 tokens), asistencia sin consumo de VRAM en PC principal. |
| **IA Local Nodo Principal (RTX 3050 6 GB CUDA)** | ~92 a 136 tokens/s | **~25 a 30 segundos** | Cargas pesadas por ráfagas, código extenso, simulación (>3.000 chars) cuando la estación está libre. |
| **Model Cloud / Frontier (ej. Model Antigravity)** | Cómputo distribuido en datacenter | **~2 a 3 segundos** | Redacción masiva de documentación, razonamiento arquitectónico global y tareas de desarrollo agéntico. |

Esta comparativa fundamenta la visión de `barto-router`: el nodo secundario y el nodo principal resuelven la privacidad y la asistencia de código habitual a coste cero y con aislamiento de recursos de la estación de trabajo, mientras que tareas de escala masiva pueden reservarse para ráfagas locales o servicios de mayor envergadura.

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

# 🗺️ 12. Plan de desarrollo v0.2

La versión **v0.2** ha completado exitosamente su fase de consolidación, modularidad e instrumentación.

## P0 — Documentación ✅
- [x] Separar resultados demostrados de funcionalidades futuras.
- [x] Eliminar afirmaciones absolutas no justificadas por las pruebas.
- [x] Documentar limitaciones experimentales.
- [x] Mantener resultados reproducibles claramente identificados.

## P1 — PolicyEngine ✅
- [x] Extraer la lógica de decisión de `router.py` hacia `policy.py`.
- [x] Definir interfaz estable `BasePolicy.decide(request, backends)`.
- [x] Implementar política inicial `ThresholdPolicy_v0.2` health-aware.
- [x] Permitir sustituir la política sin modificar el router.

## P2 — Telemetría ✅
- [x] Generación de `request_id` único por petición.
- [x] Registro estructurado en `telemetry.jsonl` y cabeceras HTTP (`X-Request-ID`, `X-Decision-Backend`, `X-Execution-Backend`, `X-Total-Time-Ms`, `X-Fallback`).
- [x] Endpoint `GET /telemetry` para consultar el historial en vivo.
- [x] Métricas de TTFT, tiempo total, tokens generados y tokens/segundo.

## P3 — Health y recuperación ✅
- [x] Estados explícitos de nodo (`ONLINE`, `BUSY`, `DEGRADED`, `OFFLINE`).
- [x] Health checks proactivos en segundo plano (Heartbeat cada 5s en `health.py`).
- [x] Medición continua de latencia LAN en milisegundos.
- [x] Endpoint `GET /health` enriquecido con latencias vivas de cada backend.
- [x] Fallback automático y preventivo ante desconexión o saturación.

## P4 — Benchmark ✅
- [x] Suite reproducible implementada en `benchmark.py`.
- [x] Escenarios automatizados: Small, Medium, Large (>13 KB) y Concurrencia (3 hilos).
- [x] Exportación formal de evidencia a `benchmark_v02_results.json`.

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

El objetivo de **v0.2** es convertir el prototipo actual en un sistema más observable, modular y reproducible mediante:

1. separación entre Router y Policy;
2. telemetría por petición;
3. health monitoring;
4. fallback;
5. benchmark reproducible.

Una vez establecida esa base, será posible evaluar de forma objetiva políticas de routing más sofisticadas.

**Estado actual: prototipo funcional con evidencia experimental.**

**Próximo objetivo: router instrumentado, modular y basado en políticas.**

---

# Licencia

Consultar los archivos de licencia del repositorio para conocer las condiciones actuales de uso y distribución.
