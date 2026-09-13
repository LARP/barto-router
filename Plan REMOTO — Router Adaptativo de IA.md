# PLAN MAESTRO — Inferencia Distribuida GPU por LAN (RPC)

**Proyecto:** Arquitectura Experimental de Asistencia Inteligente para Optimización del Tiempo Humano
**Estado:** EXPERIMENTO TÉCNICO DIRECTO (ya no investigación sobre existencia)
**Versión:** 0.2.2 — corrige §9 (ejecutable `ggml-rpc-server`, regla llama-cli primero) sobre la 0.2.1
**Fecha:** 13 de septiembre de 2026

---

## 1. Cambio fundamental respecto a la propuesta 0.1

La propuesta 0.1 planteaba *investigar si puede construirse* la división GPU→LAN→GPU.

La revisión determina que la infraestructura **ya existe de forma oficial**: `llama.cpp`
incluye un backend RPC (`ggml-rpc-server`) que distribuye pesos entre hosts por TCP,
con partición por capas en modo pipeline y reparto proporcional a la memoria libre
(`--tensor-split` como override).

Por tanto:

| Antes (v0.1) | Ahora (v0.2) |
| --- | --- |
| Hipótesis H1–H2: por demostrar | Pre-validadas upstream; no se reinventa |
| PoC propio de tensores (Pruebas 0–2) | Eliminadas; absorbidas por el RPC oficial |
| Pregunta: "¿se puede hacer?" | Pregunta: "¿en MI hardware y MI red, supera al CPU offload?" |
| Riesgo principal: viabilidad técnica | Riesgo principal: rendimiento |

## 2. Pregunta central del experimento

> ¿En el hardware real (RTX 3050 6 GB + GT 1030 2 GB) y la LAN real,
> una inferencia `llama.cpp` con RPC en modo layer ejecuta modelos que no caben
> en una sola GPU, y supera en tok/s al CPU offload del PC principal para el mismo modelo?

Sub-preguntas operativas:

- Q1: ¿La LAN soporta el tráfico de activaciones? (iperf3)
- Q2: ¿El RPC establece handshake y carga el modelo en ambos hosts? (misma versión)
- Q3: ¿El modelo que no cabe en una GPU termina la inferencia correctamente? (PASS técnico)
- Q4: ¿tok/s RPC > tok/s CPU offload para ese modelo? (PASS práctico)

## 3. Condición previa única: medición de red

```bash
# PC principal
iperf3 -s
# Nodo GT1030
iperf3 -c <IP_PC_principal>
```

| Resultado | Decisión |
| --- | --- |
| ≥ 1 Gbps real | Procede al flujo completo |
| 100 Mbps | Procede con cautela; activaciones de modelos pequeños (~MB/token) pueden ser viables en modo layer; medir en E2 antes de continuar |
| Inestable / pérdidas | Resolver red antes de cualquier experimento GPU |

## 4. Flujo experimental

```text
E0  iperf3 ................................... red (§3)
E1  Misma versión EXACTA de llama.cpp
    (mismo commit/tag) en ambos hosts ...... compatibilidad
E2  Baseline A: modelo ~1–1.5 GB solo en RTX 3050 (-ngl 99)
E3  Baseline B: mismo modelo vía CPU offload del PC principal
E4  ggml-rpc-server en GT1030 (LAN confiable, puerto 50052 restringido)
E5  Baseline C: mismo modelo con RPC (tensor-split 3,1)
    → valida el pipeline de punta a punta
E6  Modelo decisivo: > 6 GB, sin alternativa de quant que quepa
    localmente en 6 GB
    → RPC vs CPU offload del mismo modelo
E7  Barrido tensor-split 4:1, 3:1, 2:1 sobre E6
    → quedarse con el reparto de máximo tok/s
E8  (Opcional) modelo intermedio ~2.5 GB que no cabe en la GT1030 sola
```

Regla de avance: si Ei falla, no se avanza a E(i+1) hasta resolverlo.

## 5. Correcciones definitivas a la documentación

1. **RPC oficial de llama.cpp**, no PoC propio. No se escribe código de transporte.
2. **`--split-mode layer`** como estrategia inicial y única sobre LAN. El modo
`tensor/row` mueve demasiados datos por token; el tensor-parallel experimental
(meta-backend) requiere NCCL y GPUs iguales: no aplica a este caso heterogéneo.
3. **`--tensor-split` es proporción de capas, no equivalencia directa de GB.**
2 GB + 1 GB ≠ "3 GB unificados". Punto de partida 3:1 (menos capas en la
GT 1030 porque es 10–20× más lenta), barrido posterior.
4. **Misma versión exacta de llama.cpp en ambos hosts.** El wire format RPC cambia
entre releases; versiones distintas cuelgan en el handshake o crashean a mitad
de inferencia. Fijar tag/commit y anotarlo en el registro de experimentos.
5. **RPC solo dentro de LAN confiable.** Sin autenticación ni cifrado; firewall
limitando el puerto 50052 únicamente a la IP del otro host.
6. **Éxito principal = capacidad, no velocidad.** El RPC convierte "no puedo
ejecutarlo" en "puedo ejecutarlo, lento". PASS técnico no exige rapidez;
la velocidad se evalúa como métrica secundaria.
7. **Comparación práctica = RPC vs CPU offload para el mismo modelo.** Los
baselines por GPU aislada sirven para validar el pipeline (E2, E5), no como
veredicto final.
8. **Las Pruebas 0–2 (PoC de tensor/operación) quedan eliminadas** del plan:
redundantes con el RPC oficial.

## 6. Criterios de éxito

| Criterio | Nivel | Definición |
| --- | --- | --- |
| Carga y ejecución correcta | PASS técnico | El modelo > 6 GB carga en ambos hosts, genera texto coherente y termina sin OOM |
| tok/s RPC > tok/s CPU offload | PASS práctico | El distribuido es estrictamente más rápido que el offload a CPU para el mismo modelo y prompt |

El PASS técnico tiene valor propio incluso si el práctico falla: demuestra
capacidad combinada (H3) y deja medido el coste real de la comunicación (H4).

### 6.1 Métrica exploratoria (no es criterio de éxito)

Como referencia contextual se registrará, cuando aplique, la relación entre
tok/s RPC del modelo grande y tok/s del mismo modelo en un quant más pequeño
que sí quepa localmente en la RTX 3050. Esto informa la decisión "RPC vs.
degradar el quant", pero **no es un criterio de éxito**: no se fija umbral
numérico a priori porque el valor de ese ratio depende del modelo, del quant
disponible y de la tolerancia a pérdida de calidad, que son decisiones
subsecuentes a tener los datos medidos (E6–E7).

## 7. Elección del modelo decisivo (E6)

Requisitos:

- Tamaño de pesos > 6 GB (no cabe en la RTX 3050 6 GB, ni siquiera con KV mínimo).
- No existe quant de ese modelo que quepa razonablemente en 6 GB
(si cabe un Q4/Q3 usable, la comparación RPC pierde sentido).
- Quepa en 2 GB + 6 GB = 8 GB menos KV cache y overhead RPC (~0.5–1 GB).
- Candidato típico: 7–8B en quant Q8_0 (~7.5–8.5 GB de pesos).

## 8. Métricas (por corrida)

| Métrica | Herramienta | Notas |
| --- | --- | --- |
| tok/s (prompt + eval) | salida `llama-cli` / `llama-bench` | usar mismo prompt y `-n` en todas las corridas |
| VRAM usada por host | `nvidia-smi` | ambos PCs |
| bytes/s en la LAN | iperf3 (previo) + contador ggml-rpc-server | activaciones por token |
| RAM del host principal | `htop`/monitor | en CPU offload crece con el modelo |
| Correctitud | inspección de salida | coherencia, sin repetición/corte |
| Estabilidad | registro de errores | OOM, desconexiones RPC, divergencias |

Registro: fijar seed, prompt, n_predict, temperatura; anotar commit de llama.cpp,
flags y resultados en tabla única por sesión.

## 9. Comandos de referencia

```bash
# Build (AMBOS hosts, mismo tag) — -DGGML_RPC=ON es lo único extra
cmake -B build -DGGML_CUDA=ON -DGGML_RPC=ON
cmake --build build --config Release -j

# Nodo (GT1030) — ejecutable documentado: ggml-rpc-server
CUDA_VISIBLE_DEVICES=0 \
  ./build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052

# Principal — Baseline A (GPU local)
./build/bin/llama-cli -m modelo_q4.gguf -ngl 99 -p "..." -n 128 --seed 42

# Principal — Baseline B (CPU offload)
./build/bin/llama-cli -m modelo_q4.gguf -ngl 0  -p "..." -n 128 --seed 42

# Principal — E4: comprobar que el worker RPC es visible
./build/bin/llama-cli \
  --rpc 192.168.x.x:50052 \
  --list-devices

# Principal — E5 / E6: prueba distribuida
# layer es el split-mode por defecto; se explicita por claridad
# tensor-split 3,1 = proporciones 75/25 del modelo según orden de dispositivos
./build/bin/llama-cli \
  -m modelo_grande.gguf \
  -ngl 99 \
  --rpc 192.168.x.x:50052 \
  --split-mode layer \
  --tensor-split 3,1 \
  -p "..." \
  -n 128 \
  --seed 42
```

### 9.1 Regla de cliente: llama-cli primero, llama-server después

E4/E5 se validan **primero con `llama-cli`** como cliente de referencia. No se
da por hecho que `llama-server --rpc` se comporte igual: hay incidencias
reportadas en 2026 donde `llama-cli --rpc` funciona pero `llama-server --rpc`
no logra conectar al worker, incluso con el mismo commit.

Consecuencias:

- Un fallo de `llama-cli --rpc` = problema del experimento RPC (actuar sobre red/build/flags).
- Un fallo de `llama-server --rpc` con `llama-cli --rpc` funcionando = problema
  de integración del server, **no** invalida el PASS técnico ni el PASS práctico.
- `llama-server` queda como prueba posterior de integración (post-E7), no como
  prerrequisito del experimento.

## 10. Riesgos actualizados

| ID | Riesgo | Estado tras revisión |
| --- | --- | --- |
| R1 | Latencia excesiva | Sigue abierto; es LA pregunta (Q4). Mitigación: modo layer + barrido tensor-split |
| R2 | Sincronización | **Cerrado upstream**: lo resuelve ggml-rpc |
| R3 | Backend no soporta multi-host | **Cerrado**: RPC oficial existe y es mantenido |
| R4 | Buffers/ overhead RPC | Abierto; medir VRAM real vs teórica en E5 |
| R5 | Complejidad de implementación | **Muy reducido**: no hay código propio; el coste es operativo (builds, red, flags) |
| R6 | GT 1030 como cuello de botella | Abierto y probable; por eso tensor-split desigual a favor de la RTX 3050 |
| R7 | `llama-server --rpc` puede no conectar aunque `llama-cli --rpc` funcione | Abierto (incidencias 2026); mitigación: regla §9.1 — server como integración posterior |

## 11. Relación con el router A/B/C (orden de trabajo)

El experimento RPC se ejecuta **después** del router A/B/C, no en paralelo ni antes:

```text
Router A/B/C (ruta crítica actual)
        ↓ (completo y validado)
Experimento RPC E0–E8 (este plan)
        ↓ (PASS técnico + PASS práctico)
Integración: el router decide activar --rpc según tamaño de tarea
```

Aunque la infraestructura RPC ya existe y está probada upstream, mantener este orden:

- No distrae del experimento que realmente necesitas ahora (router).
- El RPC sin router sigue siendo útil manualmente (`--rpc` es un flag, no un servicio).
- La integración posterior es trivial si E6/E7 ya produjeron flags y modelos medidos.
- La integración con `llama-server` es un paso separado (regla §9.1): el router no debe depender de ella hasta validarse.

## 12. Principio rector (inalterado)

> No asumir que dos GPUs pequeñas forman una GPU grande.
> Medir si pueden cooperar de forma útil en hardware y red reales.

## 13. Próximos pasos inmediatos

1. iperf3 entre ambos PCs (E0) → registrar resultado.
2. Fijar y anotar tag de llama.cpp; build idéntico en ambos hosts (E1).
3. Preparar modelo de validación (~1–1.5 GB) y modelo decisivo (> 6 GB, §7).
4. Ejecutar E2–E5 en una sesión; registrar tabla de métricas.
5. Solo si E5 pasa: ejecutar E6–E7 y emitir veredicto RPC.

**Decisión vigente:** GO, condicionado solo a E0.