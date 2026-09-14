# INFORME TÉCNICO OFICIAL — BARTO ROUTER

|  |  |
| --- | --- |
| **Proyecto** | barto-router — Router adaptativo de inferencia local distribuida |
| **Versión evaluada** | v0.2 Consolidado |
| **Versión del informe** | v0.4 (revisada) |
| **Fecha de emisión** | 13 de septiembre de 2026 |
| **Clasificación** | Documento técnico para autorización de implementación |
| **Destino** | Dirección |
| **Alcance** | Diagnóstico, evidencia, plan de evolución y solicitud de autorización |

### Control de revisiones

| Versión | Cambio |
| --- | --- |
| v0.3 | Emisión inicial |
| v0.4 | Incorpora revisión externa: lenguaje condicional en hallazgos (N=1), reordenación de etapas 2–4, exclusión de la comparativa cloud sin metodología, métrica de latencia de input en el protocolo de VRAM, procedencia explícita de `PROTECTION_FACTOR` y criterios de abandono |

---

## 1. Resumen ejecutivo

**Barto Router** es un prototipo funcional que demuestra que un PC secundario con GPU antigua (GT 1030 2 GB, Vulkan) puede operar como nodo de inferencia local, gestionado por un router con API compatible con OpenAI ejecutándose en la estación principal (RTX 3050 6 GB, CUDA).

La versión v0.2 consolidó la base arquitectónica: Router desacoplado de PolicyEngine, telemetría estructurada por petición, health monitor con estados formales, fallback automático y suite de benchmark reproducible. La evidencia experimental es honesta y verificable, incluyendo la documentación de una estrategia descartada (inferencia RPC distribuida) por rendimiento insuficiente.

El análisis de los datos disponibles sugiere tres brechas priorizadas: (a) overhead de TTFT desproporcionado en peticiones cortas, (b) una política de routing basada en umbrales rígidos potencialmente subóptima, y (c) ausencia de rigor estadístico en las mediciones. **Ninguna de estas conclusiones es definitiva: toda la evidencia actual proviene de corridas únicas (N=1) y se formula aquí como hipótesis a validar, no como hechos establecidos.**

Este informe propone un plan de evolución en 10 etapas cuyo núcleo es convertir el router en un **sistema de routing consciente de recursos**, con un presupuesto dinámico de VRAM medido experimentalmente y una política de costo estimado calibrada con datos reales. El plan incluye criterios explícitos de éxito, fracaso y **abandono** por etapa.

**Recomendación: autorizar la implementación del plan**, con el punto de control entre Etapas 5 y 6 descrito en la sección 10.

---

## 2. Diagnóstico del estado actual

### 2.1 Arquitectura

```text
Cliente (API OpenAI)
   │
   ▼
Router (127.0.0.1:9000/v1, Windows, RTX 3050 6 GB)
   │
   ├── PolicyEngine (policy.py, ThresholdPolicy_v0.2)
   │         └── decide(request, node_states)
   ├── Health monitor (health.py, heartbeat 5 s)
   │         └── estados ONLINE / BUSY / DEGRADED / OFFLINE
   ├── Telemetría (telemetry.py → telemetry.jsonl)
   └── Backends:
         ├── Local: llama.cpp + CUDA (RTX 3050)
         └── Remoto: llama-server + Vulkan (GT 1030, LAN)
```

### 2.2 Estado de madurez por componente

| Componente | Estado | Observación |
| --- | --- | --- |
| Inferencia remota (GT 1030 Vulkan) | Demostrado | 44,6 t/s en modelo 1B Q4_K_M |
| Inferencia local (RTX 3050 CUDA) | Demostrado | 92–136 t/s |
| Comunicación LAN | Demostrado | <3 ms latencia en reposo |
| Proxy API OpenAI | Demostrado | Endpoint 127.0.0.1:9000/v1 |
| Router + PolicyEngine | Demostrado | Desacoplados, interfaz `BasePolicy.decide()` |
| Telemetría por petición | Demostrado | request_id, TTFT, tokens, decision/execution backend |
| Health monitor + fallback | Demostrado | Heartbeat 5 s, estados formales |
| Benchmark reproducible | Demostrado | 4 escenarios automatizados |
| Concurrencia (3 hilos) | Demostrado | 100 % éxito, degradación no caracterizada |
| Política basada en costo estimado | Experimental | No implementada |
| Presupuesto dinámico de VRAM | Futuro | Este informe lo prioriza |

### 2.3 Valoración general

Puntos fuertes: disciplina de evidencia (categorías DEMOSTRADO/EXPERIMENTAL/FUTURO), separación decisión/ejecución, medición antes de optimizar, documentación de descartes.

Puntos débiles: umbrales de política no calibrados (15 % GPU, 3000 caracteres), benchmarks de corrida única sin varianza, y una comparativa comercial (servicio cloud) sin metodología en el README original, **que se excluye de la evidencia de este informe** por no cumplir el estándar reproducible del proyecto.

---

## 3. Evidencia experimental disponible

### 3.1 Nodo secundario: CPU vs GT 1030 Vulkan (Llama 3.2 1B Q4_K_M)

| Métrica | AMD A8 CPU | GT 1030 Vulkan | Factor |
| --- | --- | --- | --- |
| Prompt processing | 92,76 t/s | 129,56 t/s | 1,4× |
| Generación | 7,57 t/s | 44,63 t/s | **5,9×** |
| Latencia por token | 132,1 ms | 22,4 ms | — |
| Temperatura | — | 38–43 °C | — |
| VRAM | 0 MB | 966 MiB / 2048 MiB | — |

**Conclusión evidenciada:** la GT 1030 es viable como nodo de inferencia para modelos pequeños cuantizados.

### 3.2 Experimento RPC distribuido (descartado)

| Estrategia | Velocidad |
| --- | --- |
| Capas distribuidas RPC (RTX 3050 + GT 1030) | 9,6 t/s |
| CPU local (referencia) | 62,3 t/s |

**Conclusión evidenciada:** la distribución por capas no es competitiva bajo la red actual. Decisión correcta de descarte.

### 3.3 Benchmark automatizado v0.2 (`benchmark_v02_results.json`)

| Escenario | Prompt | Backend | TTFT | Total | Rendimiento | Decisión |
| --- | --- | --- | --- | --- | --- | --- |
| Small | 51 car. | Remoto | **1.896,7 ms** | 1,90 s | 31,6 t/s | Ligera → protección |
| Medium | 240 car. | Remoto | **3.049,4 ms** | 3,05 s | 39,3 t/s | Ligera → protección |
| Large | 13.786 car. | Remoto | **31.965,5 ms** | 31,97 s | **4,7 t/s** | Estación ocupada (GPU 18 % ≥ 15 %) |
| Concurrente ×3 | 3 hilos | Remoto | 1,25 / 2,34 / 3,46 s | 3,46 s | 32→17→11,6 t/s | Cola sin errores |

**Nota metodológica:** todos los valores provienen de corridas únicas (N=1). Deben leerse como observaciones indicativas, no como estimaciones con intervalo de confianza.

### 3.4 Hallazgos del análisis (hipótesis a validar)

> **Advertencia de evidencia:** los cuatro hallazgos siguientes se derivan de los datos de la sección 3.3, es decir, de N=1 por escenario. Se formulan como hipótesis priorizadas a confirmar o refutar en las Etapas 1–3 del plan, no como hechos establecidos.

**H-1. TTFT desproporcionado en peticiones cortas (hipótesis de alta prioridad).** Con LAN en reposo a ~2 ms, un TTFT de 1,9 s en un prompt de 51 caracteres **no parece atribuible a la red**. La hipótesis dominante es overhead de conexión HTTP (ausencia de keep-alive reutilizado), cold-start o cola en llama-server. Si se confirma, la reducción del TTFT sería la mejora de mayor impacto relativo, pues representa ~100 % del tiempo total del caso de uso principal. Validación: Etapa 2.

**H-2. Costo de oportunidad de la política actual (hipótesis, basada en una corrida única).** En la observación Large, la política `ThresholdPolicy_v0.2` (`max_prompt_chars_for_secondary = 3000`, `max_gpu_util_for_local = 15`) envió 13.786 caracteres al nodo remoto (4,7 t/s, 32 s) con la estación al 18 % de GPU. Bajo las tasas locales documentadas (92–136 t/s), ese trabajo local **podría** haber requerido ~5–8 s. Una sola corrida no permite cuantificar este costo de oportunidad con confianza; tampoco permite descartar que el comportamiento fuera correcto para las condiciones del momento. Validación: Etapas 3 y 6.

**H-3. Ausencia de rigor estadístico (hecho metodológico, no hipótesis).** Los resultados provienen de corridas únicas sin medias, desviaciones ni percentiles. Los umbrales actuales no pueden ni validarse ni refutarse con esta evidencia. Esta es la única conclusión definitiva de la sección. Acción: Etapa 3.

**H-4. Degradación no lineal bajo concurrencia (hipótesis).** De 1 a 3 peticiones concurrentes, el throughput por petición cayó de 32 a 11,6 t/s. **Sugiere** un límite de capacidad del nodo muy por debajo de 3 peticiones simultáneas, pero con N=1 por nivel no es posible distinguir efecto real de ruido. Validación: Etapa 10.

---

## 4. Limitaciones conocidas

1. **Hardware del nodo:** 2 GB de VRAM limitan modelos y contexto (4096 tokens actuales).
2. **Capacidad de razonamiento:** modelos 1B adecuados para tareas simples; no sustituyen a modelos mayores.
3. **Red:** 100 Mbps actual; el RPC distribuido ya demostró la sensibilidad a este cuello de botella.
4. **Política de routing:** umbrales rígidos sin calibrar; no considera costo temporal real.
5. **Presupuesto de VRAM local inexistente:** no hay mecanismo para decidir si la estación principal puede ejecutar inferencia sin riesgo.
6. **Telemetría:** registra VRAM_before/peak pero no el mínimo libre durante la petición, impidiendo calibrar el margen de seguridad.
7. **Evidentiary gap:** toda la evidencia de rendimiento es de corrida única (ver H-3).

---

## 5. Plan de implementación propuesto

**Principio de ordenación:** primero todo el diagnóstico medible (Etapas 1–3), luego la regularización estadística (Etapa 4 en adelante se apoya en ella), y recién entonces la implementación de políticas (Etapas 6–7). No se optimiza ningún componente antes de saber si es el cuello de botella real.

### Etapa 1 — Medición de VRAM segura bajo carga interactiva *(prioridad máxima)*

Definir el presupuesto dinámico: cuánta VRAM puede consumir Barto en la estación principal sin degradar la experiencia interactiva (ver Protocolo, sección 6).

**Entregable:** tabla de presupuestos seguros por escenario de carga + parámetro `safety_margin` calibrado. **Incluye decisión de abandono documentada** (sección 7.3).

### Etapa 2 — Aislamiento del overhead de TTFT

H-1 es la hipótesis de mayor impacto potencial y su validación es un diagnóstico puro, no una optimización: no tiene sentido optimizar caché (Etapa 4) antes de saber si el cuello real está en el router, en cold-start o en la cola del servidor.

Descomponer el TTFT: (a) cliente con conexión reutilizada, (b) petición repetida inmediata (cold-start), (c) petición directa a llama-server sin router.

**Entregable:** desglose red / router / cola-servidor y medida de TTFT base por backend, ya con N=5 si la Etapa 3 corre primero (orden flexible entre 2 y 3 permitido, ambas son diagnóstico).

### Etapa 3 — Regularización estadística del benchmark

N=5 corridas por escenario con 1 de warmup descartada; reportar media ± desviación estándar y p50/p95; persistir en el JSON de resultados. Requisito previo para interpretar cualquier experimento posterior, incluida la evidencia de la Etapa 4.

**Entregable:** `benchmark_v03_results.json` con intervalos de confianza.

### Etapa 4 — KV cache cuantizado (Q8)

Evaluar `--cache-type-k q8_0 --cache-type-v q8_0` en el nodo secundario. Medir VRAM recuperada y efecto en throughput/contexto máximo. Ubicada después de la regularización estadística para que su evidencia (N=5) sea interpretable. Es una optimización de segundo orden frente a H-1, de ahí su posición.

**Entregable:** decisión adoptar/no adoptar con evidencia N=5 y criterio explícito (regresión de throughput >5 % → no adoptar).

### Etapa 5 — Calibración de throughput y latencia

Análisis offline de `telemetry.jsonl` (ahora poblado con datos regulares de la Etapa 3) para obtener tasas por backend **y su distribución de error**, que alimentan la Etapa 6. Incluye la distribución del error de estimación de tokens de salida, necesaria para calibrar `PROTECTION_FACTOR`.

**Entregable:** tabla de parámetros calibrados con procedencia (dataset + fecha), incluido el error percentilar de estimación.

### Etapa 6 — `CostEstimationPolicy`

Implementar la política blanda, con `PROTECTION_FACTOR` **derivado de la Etapa 5**, no fijado por intuición:

```text
costo_remoto = tokens_estimados / TPS_remoto + TTFT_remoto + latencia_LAN
costo_local  = tokens_estimados / TPS_local  + TTFT_local

elegir remoto si costo_remoto < costo_local × PROTECTION_FACTOR

PROTECTION_FACTOR = 1 + P90(|tokens_estimados − tokens_reales| / tokens_reales)
```

La procedencia del factor es la misma lógica que invalidó el umbral del 15 %: un parámetro que modera decisiones debe salir de datos, no de juicio. Si la Etapa 5 no produce una estimación de error confiable, la Etapa 6 no se inicia (punto de control).

**Entregable:** `CostEstimationPolicy` en `policy.py`, conmutables vía configuración sin tocar el router.

### Etapa 7 — Integración del presupuesto dinámico de VRAM

Filtro duro previo al modelo de costo:

```text
si VRAM_requerida(petición) > VRAM_libre_segura_actual → ejecutar remoto (o fallback)
```

Condicionado al resultado de la Etapa 1: si el presupuesto seguro resulta ~0 bajo carga representativa, esta etapa se reduce a documentar el abandono de la rama (sección 7.3) y el plan continúa con política remota única.

**Entregable:** routing VRAM-aware con test de unidad y evidencia en benchmark — o documento de abandono de la rama.

### Etapa 8 — Pruebas de recuperación/liberación de recursos

Verificar que la inferencia local oportunista libera VRAM al terminar y que el presupuesto se recalcula correctamente tras cada petición.

### Etapa 9 — Inyección de fallos y validación del fallback

Matar llama-server a mitad de una petición; timeouts parciales; nodo offline al momento de decidir. Medir tiempo hasta recuperación efectiva.

**Entregable:** evidencia de degradación segura.

### Etapa 10 — Concurrencia y evaluación final

Barrido 1/3/5/10/20 peticiones concurrentes con percentiles de latencia y backpressure explícito. Evaluación final contra los criterios de la sección 7.

---

## 6. Protocolo de medición de VRAM segura

### 6.1 Principio rector

El presupuesto no es la VRAM libre instantánea reportada por NVML. Es el **mínimo de VRAM libre observable bajo carga interactiva representativa, menos un margen de seguridad**, condicionado a que la aplicación principal no sufra degradación medible.

### 6.2 Variables y métricas

| Categoría | Métrica | Instrumento | Frecuencia |
| --- | --- | --- | --- |
| Recursos | VRAM libre (MiB) | NVML / `nvidia-smi --query-gpu=memory.free` | 1 Hz |
| Recursos | VRAM usada por proceso | NVML por PID | 1 Hz |
| Interactividad | FPS | contador de frames de la app | por frame |
| Interactividad | Frame-time (ms) y **varianza** | timestamps por frame | por frame |
| Interactividad | Eventos de stutter (frame-time > 2× mediana) | derivado | por frame |
| **Interactividad** | **Latencia de respuesta a input (input-to-photon) y su jitter** | **trazado de eventos de input + timestamps de presentación** | **por evento de input** |
| Estabilidad | Crashes / cierres de la app | registro manual | por sesión |

La métrica crítica es la **varianza del frame-time**, no el FPS promedio: el stutter aparece antes que cualquier crash. La **latencia de input** se añade porque una aplicación puede mantener frame-time estable mientras el jitter en la respuesta a los controles sigue siendo perceptible — especialmente en juegos sensibles al timing (competitivos, rítmicos). Si el caso de uso real es exclusivamente pasivo (render, compilación), esta métrica puede registrarse como no aplicable por sesión, pero debe justificarse explícitamente.

### 6.3 Procedimiento

Para cada nivel de presupuesto `B` en {256, 512, 1024, 1536, 2048} MiB:

1. **Base:** ejecutar la carga de Unity representativa (misma escena, misma duración, ≥10 min) **sin** inferencia. Registrar línea base de todas las métricas.
2. **Presión:** mantener la carga y reservar `B` MiB en GPU mediante proceso de prueba (CUDA o Vulkan), simulando la huella de llama.cpp.
3. **Observación:** muestrear todas las métricas durante la sesión.
4. **Criterio de aceptación de B:** FPS medio ≥ 95 % de la línea base **y** varianza del frame-time dentro de ±20 % de la línea base **y** latencia de input dentro de ±20 % de su línea base **y** cero eventos de stutter atribuibles **y** cero crashes.
5. **Determinación:** `VRAM_segura = min(VRAM_libre_observada en sesiones aceptadas) − safety_margin`.

### 6.4 Precauciones metodológicas

- **Reserva vs. uso activo:** los drivers precachean; las aplicaciones liberan perezosamente. La medición debe hacerse bajo carga sostenida, no en reposo.
- **Picos de asignación:** Unity puede reservar grandes bloques al cargar escenas; la carga representativa debe incluir transiciones de escena o cargas de texturas.
- **Shared memory fallback:** al agotarse la VRAM, Windows recurre a memoria compartida del sistema; la degradación ocurre sin crash. El criterio de stutter y de latencia de input captura este modo de fallo.
- **Repetibilidad:** mínimo 3 sesiones por nivel de presupuesto; descartar sesiones con actividad ajena registrada.

### 6.5 Extensión de telemetría

Añadir al esquema `telemetry.jsonl`:

```text
vram_free_min_during_request   # mínimo de VRAM libre mientras la inferencia corría
frame_time_variance_delta      # variación de frame-time durante la petición (si se instrumenta)
input_latency_delta            # variación de latencia de input durante la petición (si aplica)
```

Con estos campos, el `safety_margin` se calibra empíricamente correlacionando mínimos de VRAM libre contra reportes de degradación, en lugar de fijarse arbitrariamente.

---

## 7. Criterios de éxito, fracaso y abandono

### 7.1 Por etapa

| Etapa | Criterio de éxito | Criterio de fracaso |
| --- | --- | --- |
| 1 VRAM segura | Presupuesto determinado con ≥3 sesiones repetibles por nivel | Varianza entre sesiones >20 % imposibilita fijar presupuesto → repetir metodología; si persiste, ver 7.3-A |
| 2 TTFT | Overhead aislado en ≥1 componente con desglose cuantificado | TTFT sin descomponer → instrumentar router con timestamps por fase |
| 3 Benchmark N=5 | Todos los escenarios con IC reportables | Varianza alta persistente → revisar estabilidad del entorno antes de continuar; si es irreducible, ver 7.3-B |
| 4 KV Q8 | Contexto máximo aumenta o VRAM baja sin caída de throughput >5 % | Regresión >5 % → mantener caché FP16 y documentar |
| 5 Calibración | Tasas y error de estimación con distribución reportable | Error de estimación no acotable → recolección adicional antes de la Etapa 6 |
| 6 Cost policy | En re-ejecución del escenario Large, decide local cuando costo_local < costo_remoto y la VRAM lo permite | Política nueva no supera a la actual en tiempo total agregado → iterar parámetros con datos de la Etapa 5 |
| 7 VRAM-aware | Filtro correcto en tests y benchmark | — (condicionada al resultado de la Etapa 1; ver 7.3-A) |
| 9 Fallback | Recuperación <10 s en todos los casos de inyección | Fallo silencioso o pérdida de peticiones → bloqueante |
| 10 Concurrencia | Perfil de degradación documentado; límites y backpressure definidos | Colapsos no monotónicos (errores inesperados) → bloqueante |

### 7.2 Criterio global del proyecto

El plan se considera exitoso si, al final de la Etapa 10:

1. El router decide local vs. remoto basándose en costo estimado calibrado y, cuando la Etapa 1 lo permita, presupuesto de VRAM medido.
2. La decisión mejora el tiempo total agregado frente a `ThresholdPolicy_v0.2` en los 4 escenarios de benchmark, sin un solo evento de degradación de la estación principal atribuible a Barto.
3. Toda la evidencia es reproducible desde scripts versionados.

### 7.3 Criterios de abandono y ramas de decisión

El plan contempla explícitamente que su premisa central puede no sostenerse. Se definen dos salidas anticipadas:

**7.3-A Abandono de la inferencia local oportunista (rama de la Etapa 1).**
Escenario: el barrido de presupuesto determina que, bajo carga representativa de Unity, el presupuesto seguro es ~0 MiB (plausible con 6 GB compartidos: Unity, navegadores, IDE y el propio escritorio ya ocupan la mayoría).
Consecuencia planificada: las Etapas 7 y 8 se cancelan; la Etapa 6 se simplifica a una política remota única con fallback local solo en estación inactiva (detección por ausencia de carga, no por presupuesto); el proyecto se reencuadra como router de nodo remoto dedicado, lo cual **no invalida su valor**: la protección de la estación sigue siendo la función principal. Esta rama es un resultado legítimo del experimento, no un fracaso del plan, siempre que se documente con la evidencia de las sesiones.

**7.3-B Abandono por entorno no medible (rama de la Etapa 3).**
Escenario: la varianza entre corridas del benchmark permanece alta (p.ej., coeficiente de variación >25 %) después de descartar actividad ajena, indicando un entorno no controlable.
Consecuencia: detener el plan en la Etapa 3. Ninguna política calibrada sería mejor que la intuición si los datos no son estables, y sería incorrecto presentarla como basada en evidencia.

Ambas ramas tienen criterio objetivo, responsable (el ejecutor de la etapa) y producto documental esperado, de modo que la decisión de abandono se toma con datos y no por frustración a mitad de camino.

---

## 8. Riesgos técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
| --- | --- | --- | --- |
| Presupuesto de VRAM no repetible entre sesiones (ruido del SO) | Alta | Medio | Mínimo 3 sesiones por nivel; registrar actividad ajena; margen de seguridad amplio inicial; rama 7.3-A definida |
| Techo de utilidad de la inferencia local oportunista (RTX 3050 6 GB compartida con Unity) | Alta | Medio | Documentar el techo como resultado de la Etapa 1; posicionar la inferencia local como ráfagas, no carga sostenida; rama 7.3-A |
| TTFT dominado por cola de llama-server, no por el router | Media | Bajo | La Etapa 2 lo aísla; si es cola del servidor, mitigar con keep-alive y warmup del servicio |
| Estimación de tokens de salida inexacta distorsiona la política de costo | Media | Medio | `PROTECTION_FACTOR` derivado del P90 del error real de la Etapa 5; sin estimación confiable, no se inicia la Etapa 6 |
| KV Q8 introduce regresión de calidad o estabilidad | Baja | Bajo | Perplexity spot-check + benchmark comparativo N=5; decisión reversible por flags |
| Fallback silencioso en condiciones de carrera (nodo cae tras decidir) | Media | **Alto** | Etapa 9 obligatoria antes de considerar v0.3; timeout por petición con reintento idempotente |
| Cambios de llama.cpp upstream alteran las tasas calibradas | Media | Bajo | Versionar llama.cpp por commit en el README; re-correr Etapa 5 al actualizar |
| El benchmark regularizado sigue mostrando varianza irreducible | Media | Medio | Rama 7.3-B: detención del plan con documentación, en lugar de políticas sobre datos inestables |

---

## 9. Recomendaciones para la siguiente fase

1. **Exclusión editorial efectuada:** la comparativa con servicios cloud del README original carece de metodología reproducible y queda excluida de la evidencia de este informe y de la presentación a la Dirección. Si en el futuro se desea comparar contra servicios externos, requiere protocolo propio (sección 6) y sección de evidencia separada.
2. **Versionar los parámetros calibrados** (tasas, umbrales, `PROTECTION_FACTOR`, `safety_margin`) con procedencia y fecha, junto al `benchmark_v03_results.json`.
3. **No implementar políticas nuevas sobre benchmarks de corrida única**; la Etapa 3 es requisito previo de las Etapas 4–7. Las Etapas 2 y 3 son diagnóstico y pueden ejecutarse en orden flexible o en paralelo.
4. **Considerar Gigabit como enabler documentado:** el experimento RPC falló bajo 100 Mbps; si la red se migra, re-evaluar la distribución por capas como experimento aislado — no como promesa.
5. **Mantener la separación de funciones** entre análisis, decisión y ejecución observada en este proceso, incluida la revisión externa que motivó esta versión v0.4 del informe.

---

## 10. Solicitud a la Dirección

Se solicita autorización para ejecutar las Etapas 1–5 (fase de caracterización y regularización, estimada en trabajo de medición sin riesgo para los equipos), con revisión de hito antes de iniciar las Etapas 6–10 (implementación de políticas y pruebas de estrés con inyección de fallos).

Se informa además que el plan contempla dos salidas anticipadas objetivadas (sección 7.3), de modo que la autorización cubre también la posibilidad de que la evidencia indique reducir el alcance del proyecto en lugar de ampliarlo.

---

## Anexo A — Respuesta a la revisión externa (v0.3 → v0.4)

| # | Observación del revisor | Disposición |
| --- | --- | --- |
| 1 | Comparativa cloud sin metodología: retirarla ahora, no diferirla | **Aceptada.** Excluida de la evidencia (secciones 2.3 y 9.1); no se presenta a la Dirección |
| 2 | TTFT (H-1) tiene mayor impacto que KV Q8; reordenar etapas o fusionar diagnósticos | **Aceptada.** TTFT asciende a Etapa 2; KV Q8 baja a Etapa 4; se permite orden flexible 2↔3 por ser ambas diagnóstico (sección 5) |
| 3 | Los hallazgos H-2/H-4 provienen de N=1; usar lenguaje condicional | **Aceptada.** Sección 3.4 reescrita como hipótesis con advertencia de evidencia y referencias de validación por etapa; H-3 reformulado como único hecho metodológico |
| 4 | Falta métrica de latencia de input en el protocolo de VRAM | **Aceptada.** Añadida a tabla 6.2, criterio 6.3-4, precauciones 6.4 y telemetría 6.5 |
| 5 | `PROTECTION_FACTOR` sin procedencia; riesgo de repetir el umbral arbitrario del 15 % | **Aceptada.** Definido como función del P90 del error de estimación de la Etapa 5; la Etapa 6 queda condicionada al éxito de la 5 (punto de control) |
| 6 | Falta criterio de abandono si el presupuesto de VRAM resulta ~0 | **Aceptada.** Sección 7.3-A (abandono de rama local oportunista) y 7.3-B (abandono por entorno no medible), con criterio objetivo, consecuencia planificada y producto documental |

---

## Anexo B — Evidencia de validación Etapas 9 y 10 (14 sep 2026)

Metodología: router sombra en puertos 19001/19002 (mismo `ModularRouterHandler` productivo) para inyección de fallos sin tocar el router real (:9000). E10 contra router real. Todos los casos bajo criterio §7.1 (recuperación < 10 s, sin pérdida de peticiones).

### B.1 Etapa 9 — F2 Fallo reactivo (NODO cae tras decidir)

NODO_SECUNDARIO ONLINE apuntando a puerto muerto (`127.0.0.1:59999`); LOCAL_RTX real (`127.0.0.1:8081`). Script: `test_f2_fallo_forzado.py`.

| Métrica | Resultado |
| --- | --- |
| `X-Decision-Backend` | `NODO_SECUNDARIO` |
| `X-Execution-Backend` | `LOCAL_RTX` |
| `X-Fallback` | `true` |
| Tiempo total | **2,37 s** (< 10 s) |
| Status / tokens | 200, 3 tokens |

Veredicto: **PASS.** El router detectó `urlopen error 10061`, activó fallback a LOCAL_RTX y respondió sin pérdida. El sobrecosto (~2 s) corresponde al timeout de conexión TCP rechazada.

### B.2 Etapa 9 — F3 Fallback preventivo (nodo OFFLINE al decidir)

NODO_SECUNDARIO marcado OFFLINE; decisión directa sin intento de conexión. Script: `test_f3_preventivo.py`. Reproducibilidad N=3.

| Corrida | Tiempo | Decisión → Ejecución | X-Fallback |
| --- | --- | --- | --- |
| 1 | 0,33 s | LOCAL_RTX → LOCAL_RTX | false |
| 2 | 0,14 s | LOCAL_RTX → LOCAL_RTX | false |
| 3 | 0,14 s | LOCAL_RTX → LOCAL_RTX | false |

Media ~0,20 s. Corrida 1 más lenta por warmup del backend local; 2–3 estables en 0,14 s. Veredicto: **PASS 3/3.** Contraste F2/F3 confirma los dos caminos del informe: reactivo (2,37 s, con timeout) vs. preventivo (0,14–0,33 s, sin conexión).

Nota operativa: la rama preventiva retorna antes del detector de `unity.exe`, del filtro de VRAM y del modelo de costo (`policy.py:decide()`); todo el tráfico cae sobre la RTX 3050. Ensayos F2/F3 con Unity fuera de Play. El caso combinado (nodo caído + Unity en Play) queda como experimento separado con presupuesto VRAM de Etapa 1.

### B.3 Etapa 10 — Barrido de concurrencia 1/3/5/10/20

Contra router real :9000, `max_tokens=15`, timeout 120 s. Script: `test_e10_sweep.py`. Resultado persistido en `concurrency_sweep_v04.json`.

| Nivel | Total | p50 | p95 | máx | Éxito |
| --- | --- | --- | --- | --- | --- |
| 1× | 3,55 s | 3,55 s | 3,55 s | 3,55 s | 1/1 |
| 3× | 1,58 s | 1,01 s | 1,58 s | 1,58 s | 3/3 |
| 5× | 2,75 s | 1,65 s | 2,75 s | 2,75 s | 5/5 |
| 10× | 5,67 s | 3,11 s | 5,66 s | 5,66 s | 10/10 |
| 20× | 10,88 s | 5,84 s | 10,87 s | 10,87 s | 20/20 |

Veredicto: **PASS (39/39, 100 %).** Sin colapsos hasta 20×; degradación lineal de latencia con la concurrencia. Sin backpressure explícito: el router acepta todo y la cola crece; a 20× el p95 (10,87 s) roza el SLA. **Límite operativo recomendado: ≤ 10 concurrentes** (p95 5,66 s con margen). El 1× lento (3,55 s) corresponde a servidor frío; con servidor caliente el p50 baja a ~1 s (nivel 3×).

### B.4 Estado de criterios §7.1

| Criterio | Resultado |
| --- | --- |
| Etapa 9 — Recuperación < 10 s en todos los casos de inyección | **Cumplido** (F2: 2,37 s; F3: 0,14–0,33 s) |
| Etapa 10 — Perfil de degradación documentado; límites y backpressure definidos | **Cumplido** (límite ≤ 10; backpressure: pendiente de implementación, documentado como hallazgo) |

---

*Informe elaborado por el equipo de análisis técnico sobre la base de la documentación del repositorio `LARP/barto-router` (v0.2), los resultados de `benchmark_v02_results.json` y el código de `policy.py`. Versión v0.4 revisada con incorporación de revisión externa. Anexo B agregado el 14 sep 2026 con evidencia de validación Etapas 9–10.*
