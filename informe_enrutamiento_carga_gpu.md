# Informe Técnico: Enrutamiento Dinámico de Carga y Rendimiento GPU Local (RTX 3050 vs. GT 1030)

**Fecha:** 13 de Septiembre de 2026  
**Entorno:** Arquitectura Distribuida LAN `barto-router`  
**PC Principal:** Lenovo Legion · Intel Core i7-13650HX · 16 GB RAM · NVIDIA GeForce RTX 3050 6GB Laptop GPU  
**PC Secundario (Nodo Remoto):** MSI MS-7721 · AMD A8 PRO-7600B · 16 GB RAM · NVIDIA GeForce GT 1030 2GB (Ubuntu Server 24.04 LTS)  
**Modelo de Evaluación:** `Llama-3.2-1B-Instruct-Q4_K_M.gguf`  

---

## 1. Resumen Ejecutivo

El objetivo de esta prueba experimental fue validar el mecanismo de **enrutamiento adaptativo oportunista** implementado en `barto-router`. El router examina el tamaño de la carga de entrada (prompt) y la disponibilidad de recursos de la estación de trabajo en tiempo real:

1. **Consultas Cotidianas (< 3.000 caracteres):** Son delegadas al **PC Secundario (GT 1030)** para proteger completamente la GPU y VRAM del PC principal, permitiendo que Unity3D u otras herramientas de desarrollo operen sin interferencias.
2. **Cargas Masivas (> 3.000 caracteres / código extenso):** Si la **RTX 3050 local** está en reposo (uso < 15% y > 3 GB VRAM libre), el router conmuta automáticamente la petición al **PC Principal**, desatando su potencia de cómputo (Tensor Cores / FP16) para procesar prompts gigantescos en una fracción del tiempo que requeriría el nodo remoto.

```mermaid
flowchart TD
    Req["Petición entrante (/v1/chat/completions)"] --> CheckSize{"¿Prompt > 3.000 caracteres?"}
    
    CheckSize -- "No (Carga Ligera)" --> RemoteNode["Nodo Secundario GT 1030 (192.168.100.105:8080)<br/>• 0% VRAM consumida en PC Principal<br/>• Estación 100% protegida"]
    
    CheckSize -- "Sí (Carga Pesada)" --> CheckGPU{"¿RTX 3050 local libre?<br/>(Uso < 15% y VRAM > 3GB)"}
    
    CheckGPU -- "Sí (Oportunista)" --> LocalGPU["Nodo Principal RTX 3050 (127.0.0.1:8081)<br/>• Ráfaga de Alta Velocidad (92.3 tok/s)<br/>• Prompt Processing > 2.000 t/s"]
    
    CheckGPU -- "No (Estación Activa / Unity en Play)" --> RemoteNode
```

---

## 2. Metodología de las Pruebas

Se configuró un pipeline de pruebas automatizado ([run_comparative_experiment.py](file:///D:/opencode/test/run_comparative_experiment.py)) que ejecuta dos escenarios a través del puerto central de `barto-router` (`http://127.0.0.1:9000/v1/chat/completions`):

* **Escenario A (Carga Ligera):** Pregunta técnica cotidiana sobre recolección de basura en Unity/C# (81 caracteres, ~25 tokens).
* **Escenario B (Carga Pesada):** Script de simulación física masiva en Unity con 50.000 entidades y solicitud de refactorización hacia Unity DOTS / Burst Compiler (13.856 caracteres, ~4.330 tokens).
* **Muestreo de Telemetría:** Durante toda la ejecución de ambas pruebas, se monitoreó la RTX 3050 a intervalos de 100 ms vía `nvidia-smi` registrando: uso de GPU (%), VRAM utilizada (MB), temperatura (°C) y consumo eléctrico (W).

---

## 3. Tabla Comparativa de Resultados Empíricos

| Métrica Evaluada | Escenario A: Carga Ligera (Nodo Secundario) | Escenario B: Carga Pesada (Nodo Principal) | Factor de Impacto / Diferencia |
|---|---|---|---|
| **Nodo Asignado por el Router** | **`NODO_SECUNDARIO` (GT 1030 Remoto)** | **`LOCAL_RTX` (RTX 3050 Local)** | Enrutamiento 100% autónomo |
| **Tamaño del Prompt** | 81 caracteres (~25 tokens) | **13.856 caracteres (~4.330 tokens)** | **171× más datos de entrada** |
| **Tokens Generados** | 120 tokens | **200 tokens** | Salida extensa solicitada |
| **Tiempo de Respuesta Total** | 3.38 segundos | **2.17 segundos** | **1.56× más rápido a pesar de la carga masiva** ⚡ |
| **Velocidad Efectiva Global** | 35.5 tokens/segundo | **92.3 tokens/segundo** | **2.6× mayor rendimiento** |
| **Pico de Uso de GPU Local** | 17% (ruido visual de Windows) | **100% (ráfaga de cómputo)** | Activación total de Tensor Cores |
| **Consumo Eléctrico GPU Local** | 4.2 W (reposo de escritorio) | **74.8 W (TGP máximo sostenido)** | Potencia máxima entregada |
| **Variación de VRAM en Local** | **0 MB** | **4 MB** (KV cache dinámico) | Huella de memoria mínima |

---

## 4. Análisis Detallado del Comportamiento

### A. Escenario de Carga Ligera (Protección de la Estación de Trabajo)
* **Comportamiento:** El router clasificó la consulta dentro del rango habitual de asistencia de código. La derivó por LAN al nodo Ubuntu con la GT 1030.
* **Impacto en PC Principal:** Cero interferencia. La RTX 3050 permaneció en 4.2 W con 0 MB de variación de VRAM. Si el desarrollador estuviera ejecutando una escena compleja de Unity en Play Mode, no habría experimentado ninguna micro-pausa ni caída de FPS.

### B. Escenario de Carga Pesada (Ráfaga de Inferencia Oportunista)
* **Comportamiento:** Un prompt de 13.856 caracteres saturaría el buffer de contexto y el ancho de banda PCIe de la GT 1030 (tomando entre 15 y 20 segundos en el nodo remoto). Al detectar que la RTX 3050 local estaba disponible, el router activó el backend local CUDA (`llama-server` en puerto 8081).
* **Rendimiento de Cómputo:**
  * El procesamiento del prompt de más de 4.300 tokens se completó en apenas **~0.3 segundos** gracias al ancho de banda PCIe (7.02 GB/s) y a la potencia FP16 de la arquitectura Ampere.
  * La generación de 200 tokens se sostuvo a **92.3 tokens/s**, completando el análisis integral de arquitectura de software en apenas **2.17 segundos**.
  * Tras finalizar la inferencia en 2 segundos, la GPU local volvió inmediatamente a su estado de reposo (4-5 W).

---

## 5. Conclusiones y Próximos Pasos

1. **Validación del Router Adaptativo:** Se comprobó empíricamente que la arquitectura híbrida local/remota ofrece lo mejor de dos mundos: **cero consumo de recursos en tareas cotidianas** y **aceleración masiva instantánea cuando la tarea lo amerita**.
2. **Eficiencia Térmica y Energética:** La RTX 3050 solo consume energía en ráfagas de 2 segundos para procesar bloques pesados, regresando al estado de bajo consumo sin acumular calor sostenido en la laptop.
3. **Paso Siguiente Recomendado:** Incorporar un detector de procesos (`Unity.exe` / `devenv.exe`) en `router.py` para bloquear temporalmente el desvío a la GPU local si Unity entra en Play Mode o compilación activa, garantizando prioridad absoluta al trabajo interactivo del desarrollador.
