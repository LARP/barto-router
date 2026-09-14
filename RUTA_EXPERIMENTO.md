# Ruta del experimento — Presupuesto seguro de VRAM (v0.5-experimental)

> Derivado de `Plan experimental.md` §6. Checkpoint base: tag `v0.4-stable`.
> Objetivo: medir cuánta VRAM puede usar un LLM local en RTX 3050 6GB sin degradar Unity, y fijar `safety_margin` + filtro de `CostEstimationPolicy`.

## Fases

### F0 — Baseline B=0 (sin LLM)
- Script: `measure_unity_interactive.py`
- Medir en Unity en reposo + carga típica: frame-time medio ± IC, p95/p99, input latency, VRAM libre min.
- Salida: `resultados/f0_baseline.json` (N=3 sesiones).
- Criterio: CV < 10% entre sesiones, si no, estabilizar escena Unity antes de seguir.

### F1 — Curva dosis-respuesta B ∈ {0.5, 1, 1.5, 2, 2.5, 3} GB
- Modelo: Llama 3.2 1B Q4_K_M, contexto corto. N=3 por punto.
- Scripts: `benchmark_kv_q8.py` + `measure_unity_interactive.py` en paralelo, log a `telemetry.jsonl`.
- Métricas por B: frame-time medio ± IC, varianza, input latency, min VRAM libre, t/s LLM.
- Salida: `resultados/f1_curva_B.json` + figura `degradacion(B)`.
- Regla de parada: si frame-time p95 sube >10% vs F0 en 2 puntos consecutivos, no subir más B en esa sesión.

### F2 — Fallo forzado (over-budget)
- 1 sesión deliberada por encima del B seguro de F1.
- Caracterizar shared-memory fallback: ¿crash, stutter, OOM? Mismo instrumento que F1.
- Salida: `resultados/f2_fallo.json`.

### F3 — Liberación bajo presión
- Pico de VRAM de Unity *durante* inferencia local.
- Medir: t_detección, t_liberación, petición perdida vs reanudada (conectar con `health.py` + fallback <10s SLA).
- Salida: `resultados/f3_liberacion.json`.

### F4 — KV f16 vs q8_0
- Repetir F1 en 2 puntos (B=1 y B=2) con `--cache-type-k/v q8_0`.
- Hipótesis: q8 duplica contexto útil con igual degradación.
- Salida: `resultados/f4_kv_q8.json`. Criterio regresión <5%.

## Convenciones
- `resultados/` versionado en git (JSON pequeños). Binarios/zips/gguf NO se commitean.
- Protocolo versionado aquí; cambiar protocolo = bump de sección + commit separado.
- Cierre de etapa: actualizar `README.md` §16 + tag `v0.5-fN`.

## Estado
- [x] Checkpoint `v0.4-stable`
- [x] F0 baseline — RE-MEDIDO en Play 2026-09-13: N=3, VRAM libre min 4153±3 MB (CV 0.07%), GPU 33.5%, presupuesto seguro ~2653 MB. Supera al F0-editor (4211 MB); usar este como baseline oficial. Ver `resultados/f0_play_baseline.json`.
- [x] F1 curva — REPETIDA en Play 2026-09-13: B≈1.2GB (ctx8192) libre min 2955 MB, GPU 33.4%, presupuesto 1455 MB (SÍ local, 0.62s/48tok); B≈2.4GB (doble instancia) libre min 1767 MB, GPU 32.2%, presupuesto ~267 MB (NO local). Rodilla confirmada en Play. Ver `resultados/f1_play_*`.
- [ ] F2 fallo
- [ ] F3 liberación
- [ ] F4 KV q8
