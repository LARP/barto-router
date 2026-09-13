# INFORME TÉCNICO/BIBLIOGRÁFICO — INFERENCIA OPORTUNISTA SOBRE VRAM COMPARTIDA DINÁMICAMENTE

| | |
|---|---|
| **Proyecto** | Barto Router |
| **Consulta** | Carta al experto del Director del proyecto (13-sep-2026) |
| **Pregunta central** | ¿Es posible utilizar dinámicamente ~2 GB de VRAM temporalmente disponible de una GPU compartida con una aplicación interactiva, mediante un runtime/router que mida el presupuesto seguro, ejecute inferencia oportunista y libere el recurso bajo presión? |
| **Fecha de emisión** | 13 de septiembre de 2026 |
| **Autor** | Consultor experto externo |

---

## 0. Resumen de la evaluación

**Respuesta corta:** la formulación exacta de la pregunta **no ha sido encontrada tal cual en la literatura**. Sin embargo, cada uno de sus componentes tiene antecedentes sólidos y publicados. La propuesta de Barto Router es una **integración novedosa de mecanismos conocidos aplicados a un escenario (GPU de consumo compartida con aplicación 3D interactiva, con el presupuesto de VRAM *medido* mediante métricas de interactividad) que la literatura académica no caracteriza**. No corresponde reclamar novedad científica amplia; sí corresponde afirmar que existe un **espacio experimental concreto y delimitado que no está caracterizado**, y que el plan de Barto Router está bien diseñado para producir esa caracterización con rigor.

Se recomienda incorporar la línea al plan formal, con el diseño experimental mínimo de la sección 8.

---

## 1. Antecedentes directos

Se entiende por "antecedente directo" un sistema que ejecute cómputo secundario en una GPU compartida con una aplicación primaria protegida, con gestión dinámica de memoria o cómputo. Existen, pero **ninguno en la configuración exacta de Barto Router** (GPU de consumo única + aplicación 3D interactiva + presupuesto de VRAM medido por frame-time + inferencia LLM + liberación dinámica).

### 1.1 Compartición GPU con protección QoS — antecedente conceptual más cercano

**Baymax (SOSP 2015)** — *QoS Awareness and Increased Utilization for Non-Preemptive Accelerators in Warehouse Scale Computers*. Runtime que co-ubicó cargas interactivas ("user-facing": consultas DNN, IPA/Sirius) con cargas de throughput (Rodinia) en la misma GPU K40, garantizando el percentil 99 de latencia de la carga interactiva mediante: predicción de duración de kernels, *QoS headroom* calculado periódicamente, reordenación de kernels que no quebranten el presupuesto temporal, y gestión de contención PCIe. Resultado: +91,3 % de utilización del acelerador sin violaciones QoS significativas (<5 % de co-ubicaciones con degradación <2 %).

Relevancia para Barto: es el antecedente conceptual del "filtro duro de recursos + carga oportunista" — pero opera sobre **tiempo de cómputo (SM)**, no sobre **presupuesto de VRAM**, y su carga protegida es de *servicio* (latencia de consulta), no una **aplicación gráfica interactiva con frame-time**.

### 1.2 Escalado dinámico de memoria GPU para co-ubicación

**AntMan (OSDI 2020)** — *Dynamic Scaling on GPU Clusters for Deep Learning* (Alibaba). Co-ubica trabajos de entrenamiento en GPUs compartidas mediante: *dynamic memory scaling* (los picos de memoria del trabajo garantizado se cachean temporalmente en memoria del host y se devuelven a VRAM tras la reasignación) y lanzamiento oportunista de kernels en huecos de cómputo. Mejora de utilización de memoria GPU +42 % y de cómputo +34 % en producción. Limitación señalada por la literatura posterior: su coordinación por fronteras de mini-batch **no es aplicable a inferencia** (RPE, 2024).

Relevancia: demuestra que la VRAM es escalable dinámicamente entre procesos cooperando con el framework — pero requiere modificar el framework de deep learning (intrusivo), es a escala de clúster, y para entrenamiento.

### 1.3 Compartición transparente con sobre-suscripción de memoria

**TGS (NSDI 2023)** — *Transparent GPU Sharing in Container Clouds for Deep Learning Workloads*. Compartición de GPU transparente para cargas de producción + oportunistas en nubes de contenedores. Incluye control de tasa adaptativo que "protege los trabajos de producción con poco overhead mientras proporciona los recursos restantes a trabajos oportunistas", y **memoria unificada transparente que protege trabajos de producción bajo sobre-suscripción de memoria GPU** (hasta 15× de mejora vs. MPS bajo sobre-suscripción).

Relevancia: es probablemente el antecedente **más cercano en memoria** — sobre-suscripción de VRAM con protección de la carga primaria — pero de nuevo en clúster de contenedores, cargas de entrenamiento, y sin carga interactiva gráfica.

### 1.4 Inferencia LLM sobre recursos reclamables (preemptible/opportunistic)

**SpotServe (ASPLOS 2024)** — primer sistema de serving distribuido de LLMs sobre instancias *spot* (reclamables por el proveedor). Introduce *stateful inference recovery*: la inferencia interrumpida se reanuda a nivel de token reutilizando KV cache migrada, aprovechando el período de gracia de ~30–120 s. Reduce P99 entre 2,4× y 9,1× y ahorra 54 % de coste vs. on-demand.

**Miao et al. (2024)** — serving de LLM exclusivamente sobre instancias spot, con migración de estado a otros nodos durante períodos de gracia.

**Parsl-TaskVine (arXiv 2509.13201, 2025)** — inferencia LLM sobre **clústeres oportunistas de GPU heterogéneas** (567 GPUs, HTCondor como *backfiller* sobre máquinas no asignadas), con gestión de contexto distribuido y evicción inmediata de trabajadores al ser reclamados.

**MorphCloud-LLM (MDPI Electronics, 2026)** — serving elástico de LLM con recuperación transparente de preemption sobre spot instances.

Relevancia: esta familia resuelve el problema **temporal** de la reclamación (qué hacer cuando el recurso desaparece: migrar, guardar progreso, reanudar). **Ninguno abre la pregunta espacial de memoria de Barto Router**: ¿cuánta VRAM es segura *mientras* el recurso está disponible? Y la granularidad de reclamación es la instancia/nodo, no el presupuesto de memoria dentro de una GPU compartida con un juego.

### 1.5 Práctica industrial: inferencia junto a juegos en la misma GPU

NVIDIA embarca desde hace años inferencia ejecutándose concurrente con juegos en la misma GPU de consumo (DLSS, Frame Generation, Broadcast, ACE para NPCs). Esto demuestra **viabilidad física** de la coexistencia, pero con presupuestos fijos y controlados por el vendor, sin medición dinámica de presupuesto seguro ni liberación bajo presión — es ingeniería cerrada, no un mecanismo medible y reusable. No constituye antecedente publicado del mecanismo de presupuesto dinámico.

### 1.6 Gestión de memoria de inferencia bajo presupuesto estático

**vLLM / PagedAttention (SOSP 2023)** — paginación del KV cache inspirada en memoria virtual de SO, con *preemptive request scheduling* (desalojar y reanudar requests) y cero fragmentación interna. Gestión dinámica de memoria **dentro** de un presupuesto total asignado al servidor.

**FlexGen (ICML 2023)** — motor de alto throughput con memoria GPU limitada: agrega GPU+CPU+disco y resuelve un problema de programación lineal para colocar pesos, KV cache y activaciones bajo un presupuesto dado; compresión a 4 bits. Demostró OPT-175B en una GPU de 16 GB.

**prima.cpp (arXiv 2504.08791, 2025)** — inferencia distribuida 70B en clústeres domésticos de bajos recursos, con presión de memoria <6 % explícitamente orientada a **no degradar las demás aplicaciones del dispositivo** ("prioritize user experience... better suited for user devices"). Antecedente más afín en espíritu de coexistencia con apps de usuario, aunque su contención es de RAM/VRAM agregada en clúster, no VRAM compartida con una app 3D en la misma GPU.

**llama.cpp `--fit` / `--fit-target` (upstream, 2024–2026)** — el runtime **sondea la VRAM libre al arrancar** y calcula la colocación de capas (`-ngl`, override de tensores a CPU) dejando un margen objetivo en MiB. Es un precedente directo del concepto "presupuesto medido", pero **estático**: se mide una vez al inicio y no reacciona a la presión creciente de una aplicación interactiva en ejecución. Nota empírica de la comunidad: un `--fit-target` de 128 MiB sobrevivió benchmarks cortos y luego falló con OOM en sesión larga; 512 MiB resultó estable — ancla empírica directamente útil para dimensionar el `safety_margin` de Barto.

### 1.7 Tabla de cobertura: qué está resuelto y qué no

| Componente de la pregunta de Barto | Estado | Referencias |
|---|---|---|
| Inferencia LLM viable en ~2 GB de VRAM (cuantización, offloading, KV q8) | **Resuelto** | llama.cpp; FlexGen; prima.cpp; guías de KV quant (q8_0 ≈ 0,5× VRAM de KV) |
| Compartir GPU entre carga primaria protegida y carga oportunista | **Resuelto (datacenter, cómputo/memoria de entrenamiento)** | Baymax; AntMan; TGS; Salus; Gandiva |
| Reaccionar a reclamación del recurso (migración, recovery) | **Resuelto (granularidad instancia/nodo)** | SpotServe; Miao 2024; Parsl-TaskVine; MorphCloud |
| Medir VRAM libre como presupuesto (una vez) | **Resuelto (estático, sin contención)** | llama.cpp `--fit` |
| **Presupuesto dinámico de VRAM medido por QoS de app interactiva (frame-time, input latency), con inferencia oportunista y liberación bajo presión, en GPU de consumo única** | **No encontrado en literatura** | — (espacio de Barto) |

---

## 2. Terminología de búsqueda recomendada

La pregunta cruza tres comunidades que no comparten vocabulario. Términos por comunidad:

**Sistemas operativos / arquitectura de computadores (GPU sharing):**
`GPU memory oversubscription` (la más fértil para el eje memoria), `spatial multitasking / spatial sharing`, `GPU co-location`, `GPU co-scheduling`, `QoS-aware GPU scheduling`, `opportunistic GPU computing`, `scavenging / backfilling (HTCondor)`, `MPS / MIG / time-slicing`, `fractional GPU`, `GPU virtualization`, `unified memory paging`.

**Serving de LLM (memoria y reclamación):**
`preemptible / spot instance LLM serving`, `stateful inference recovery`, `KV cache paging / eviction`, `KV cache quantization`, `LLM offloading`, `elastic inference`, `dynamic memory scaling`, `reclaim-aware scheduling`.

**Gráficos interactivos + QoS:**
`interactive GPU resource sharing`, `frame-time QoS`, `game + inference co-residency`, `input-to-photon latency`, `GPU scheduling for mixed workloads`.

Combinaciones de búsqueda efectivas: `("GPU memory oversubscription" OR "dynamic memory scaling") AND (inference OR LLM) AND (interactive OR QoS)`; `(opportunistic OR scavenging) AND (GPU) AND (LLM inference) AND (eviction OR reclamation)`.

**Aviso sobre la búsqueda:** los resultados negativos de búsqueda no prueban inexistencia. El espacio de Barto está en la intersección de comunidades que publican en venues distintos (SOSP/OSDI/NSDI vs. ASPLOS/MLSys vs. gráficos). La conclusión de "no encontrado" debe mantenerse como *"no localizado tras búsqueda estructurada"*, no como teorema.

---

## 3. ¿Contribución diferenciable o integración de mecanismos conocidos?

**Evaluación:** mayoritariamente **ingeniería de integración**, con **un núcleo de contribución experimental acotado**.

- *Ingeniería (resuelto):* ejecutar LLMs en 2 GB (cuantización, KV q8, offloading parcial); sondear VRAM libre; desalojar y reanudar peticiones; migrar bajo reclamación; proteger una carga primaria mediante presupuesto duro.
- *Ingeniería (no resuelto pero sin novedad conceptual):* el router que compone todo esto. Es un sistema bien diseñado, no un resultado científico.
- *Contribución experimental potencial:* **la caracterización cuantitativa del presupuesto seguro** — la función que va de `(presupuesto B, carga interactiva)` a `(degradación medible)`, incluyendo los modos de fallo específicos de la coexistencia (shared memory fallback silencioso, picos de asignación de Unity, jitter de input). Nadie publica (búsqueda estructurada) números de "cuánta VRAM puede consumir un LLM 1B–3B en una RTX 3050 de 6 GB antes de degradar un juego/Unity de forma medible". Ese dataset, producido con protocolo reproducible (el de la sección 6 del informe v0.4), **sería un artefacto publicable** — no necesariamente como paper de sistema, sí como benchmark técnico/reporte de caracterización, muy en la línea de informes de la comunidad de inferencia local (perfiles L3MS, llama.cpp guides).

La tesis defendible ante un revisor es: *"la combinación exacta existe parcialmente en producción cerrada (NVIDIA) y sus piezas existen abiertamente en datacenter; la medición abierta y reproducible del presupuesto seguro en GPU de consumo compartida con carga 3D interactiva no está caracterizada."*

---

## 4. Sobre la escala de 1–2 GB

**Sí tiene sentido, con matices:**

- En una GPU de 6 GB compartida con Unity + navegador + IDE, el régimen operativo real probablemente es **B ∈ [0, ~2,5 GB]**. Fijar el laboratorio en 1–2 GB acierta con el centro del régimen.
- Recomendación: **extender el barrido hasta B = 0** (no 256 MB como mínimo), porque B ≈ 0 es el resultado plausible del riesgo 7.3-A y debe medirse, no asumirse; y **hasta B = 3 GB** para delimitar el techo superior.
- El rango 1–2 GB además es el único donde el trade-off es interesante: con 1 GB cabe un 1B Q4 + contexto corto (sección 3.1 del README: 966 MiB ya medidos); con 2 GB, KV cache q8 (`--cache-type-k/v q8_0`, ~0,5× de huella de KV) permite contexto doble — la Etapa 2 del plan interactúa directamente con el presupuesto.
- Ancla empírica disponible: en la comunidad llama.cpp, `--fit-target 128` MiB falló con OOM en sesión larga mientras `512` MiB fue estable; esto sugiere que el `safety_margin` mínimo creíble está en el orden de **0,5 GB**, no en decenas de MiB — hipótesis a verificar en el barrido de Barto.

---

## 5. Respuestas numeradas al Director

**1. Antecedentes.** No se ha localizado ningún sistema que implemente exactamente la formulación (presupuesto de VRAM dinámico, medido por QoS de app interactiva, en GPU de consumo única, con liberación bajo presión y router/fallback). Antecedentes parciales directos: Baymax (co-ubicación QoS), AntMan y TGS (memoria GPU dinámica/sobre-suscripción con protección), SpotServe y familia spot/opportunistic (reclamación y recovery), vLLM/FlexGen/prima.cpp (inferencia bajo presupuesto), llama.cpp `--fit` (presupuesto estático medido). Sección 1.7 tabula la cobertura.

**2. Terminología.** Sección 2. Las tres más productivas: `GPU memory oversubscription`, `opportunistic GPU computing`, `preemptible/spot LLM serving`. El eje que Barto aporta (QoS de app 3D interactiva como señal de control) se busca mejor con términos de gráficos: `frame-time QoS`, `mixed workloads GPU scheduling`.

**3. ¿Contribución o integración?** Integración de mecanismos conocidos + un artefacto experimental acotado caracterizable: el dataset del presupuesto seguro. No reclamar novedad de sistema; sí la del artefacto de caracterización, si el protocolo se ejecuta con el rigor ya exigido (N≥3 sesiones, IC, protocolo versionado).

**4. Escala de 2 GB.** Sí, como régimen central; extender a [0, 3 GB] para acotar ambos extremos. Ver sección 4.

**5. ¿Incorporar a Barto Router?** Sí. Recomendación concreta de diseño experimental mínimo: sección 8.

---

## 6. Diseño experimental mínimo recomendado

El protocolo de la sección 6 del Informe Técnico v0.4 (barrido de presupuesto con métricas de frame-time, input latency y criterios de aceptación) ya constituye el núcleo. Para que el resultado establezca diferencia con evidencia respecto al estado del conocimiento, recomiendo añadir cuatro elementos que la literatura no reporta:

1. **Curva dosis-respuesta completa y repetida.** Para cada B ∈ {0, 0,5, 1, 1,5, 2, 2,5, 3} GB (nota: GB, no solo potencias de dos), 3 sesiones, reportando media ± IC del frame-time, varianza, input latency y *min* de VRAM libre. Producto: figura `degradación(B)` reproducible — este es el artefacto que no existe publicado.
2. **Modo de fallo forzado documentado.** Al menos una sesión deliberadamente por encima del presupuesto seguro para caracterizar el *shared memory fallback* (degradación sin crash) con el mismo instrumento. La literatura de oversubscription lo menciona; una medición abierta en este contexto no existe.
3. **Liberación bajo presión medida.** Inyectar un pico de demanda de VRAM de la app interactiva *durante* una inferencia local; medir (a) tiempo de detección, (b) tiempo de liberación efectiva, (c) pérdida o reanudación de la petición. Esto conecta la línea con la familia SpotServe (recovery) pero a granularidad de presupuesto de memoria, donde la literatura no tiene números.
4. **Interacción con KV cache cuantizado (Etapa 2 del plan).** Reportar la curva `degradación(B)` con caché f16 y con q8_0: si q8 permite duplicar contexto dentro del mismo presupuesto seguro, ese punto de datos (throughput ganado vs. presupuesto ocupado) tampoco está reportado en literatura para este escenario.

Con estos cuatro elementos, el deliverable de la Etapa 1 del plan deja de ser un parámetro de configuración y pasa a ser **evidencia experimental potencialmente publicable** — cumpliendo exactamente el objetivo declarado en la consulta: determinar con rigor dónde termina el conocimiento existente y dónde comienza la pregunta propia.

---

## 7. Referencias

1. Cheng Li et al., **Baymax: QoS Awareness and Increased Utilization for Non-Preemptive Accelerators in Warehouse Scale Computers**, SOSP 2015. https://www.cs.sjtu.edu.cn/~chen-quan/PDF/Conferences/C2.pdf
2. Wencong Xiao et al., **AntMan: Dynamic Scaling on GPU Clusters for Deep Learning**, OSDI 2020. https://www.usenix.org/conference/osdi20/presentation/xiao
3. Bingyang Wu et al., **TGS: Transparent GPU Sharing in Container Clouds for Deep Learning Workloads**, NSDI 2023. https://www.usenix.org/system/files/nsdi23_slides_wu-bingyang.pdf
4. **Predicting workload colocations under GPU spatial sharing** (análisis comparativo de AntMan/Salus/Gandiva y limitaciones para inferencia), 2024. https://bhan.im/static/publications/preprint/RPE.pdf
5. Woosuk Kwon et al., **Efficient Memory Management for Large Language Model Serving with PagedAttention (vLLM)**, SOSP 2023. https://arxiv.org/pdf/2309.06180
6. Ying Sheng et al., **FlexGen: High-Throughput Generative Inference of Large Language Models with a Single GPU**, ICML 2023. https://proceedings.mlr.press/v202/sheng23a.html
7. **FlexLLMGen** (implementación FlexGen). https://github.com/FMInference/FlexLLMGen
8. **SpotServe: Serving Generative Large Language Models on Preemptible Instances**, ASPLOS 2024. https://arxiv.org/html/2311.15566
9. **Scaling Up Throughput-oriented LLM Inference Applications on Heterogeneous Opportunistic GPU Clusters with Pervasive Context Management (Parsl-TaskVine)**, arXiv 2509.13201, 2025. https://arxiv.org/html/2509.13201
10. **MorphCloud-LLM: Elastic Spot-Instance-Aware LLM Serving with Transparent Preemption Recovery**, MDPI Electronics 15(17):3865, 2026. https://www.mdpi.com/2079-9292/15/17/3865
11. Zonghang Li et al., **PRIMA.CPP: Speeding Up 70B-Scale LLM Inference on Low-Resource Everyday Home Clusters**, arXiv 2504.08791, 2025. https://arxiv.org/html/2504.08791v1
12. **Local LLM Inference Optimization: The Complete Guide** (evidencia empírica de `--fit-target`, KV q8_0 ≈ 0,5×, OOM por margen insuficiente), 2026. https://carteakey.dev/blog/local-inference/local-llm-optimization/
13. **llama.cpp discussion #9784** (huella de VRAM y comportamiento de mmap en Windows vs. Linux). https://github.com/ggml-org/llama.cpp/discussions/9784

---

*Informe emitido en respuesta a la consulta abierta del Director. Las afirmaciones de no-existencia se limitan a "no localizado tras búsqueda estructurada en literatura de sistemas (SOSP/OSDI/NSDI/ASPLOS), serving de LLM y práctica industrial publicada", fecha de corte: 13-sep-2026.*
