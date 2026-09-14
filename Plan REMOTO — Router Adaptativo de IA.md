# PLAN REMOTO — Router Adaptativo de IA (STUB)

**Estado:** SUPERSEDED — documento fósil conservado como puntero. No usar como plan de trabajo.

El contenido original de este archivo (v0.2.2, 13 sep 2026) era idéntico a
[`plan mejora.md`](plan%20mejora.md) v0.2.2 y quedó desactualizado. La versión vigente es
**`plan mejora.md` v0.2.4**, que registra:

- Decisión: **NO-GO** al flujo RPC E0–E8 (re-medición de un descarte ya evidenciado, informe §3.2).
- **E0 verde:** iperf3 nodo→principal **939 Mbits/sec** (corrige el supuesto de 100 Mbps).
- **E0.5 rojo:** tiempo por capa GT 1030 ≈ 1,41 ms vs RTX 3050 ≈ 0,40 ms
  (ratio **≈3,5×**, corrige el "10–20×" citado en §5.3 de la v0.2.2);
  el 25% de capas en la GT consumiría el 54% del tiempo → R6 cierra el plan.
- Evidencia: §14 / §14.1 de `plan mejora.md`, Anexo B del informe v0.4.

Historial completo preservado en git (`git log -- "Plan REMOTO — Router Adaptativo de IA.md"`).
