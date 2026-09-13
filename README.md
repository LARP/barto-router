# Barto Router

**Router experimental de inferencia local distribuida para hardware heterogéneo.**

Barto Router permite utilizar recursos de cómputo de distintas máquinas de una red local para ejecutar inferencia, evitando que todas las cargas de IA recaigan necesariamente sobre la GPU principal de la estación de trabajo.

El proyecto nació como un experimento práctico para separar **desarrollo** e **inferencia**:

```text
┌─────────────────────────────┐
│       PC PRINCIPAL          │
│                             │
│ Unity / IDE / navegador     │
│ RTX 3050                    │
│                             │
│        Barto Router         │
└──────────────┬──────────────┘
               │ LAN
               ▼
┌─────────────────────────────┐
│       PC SECUNDARIO         │
│                             │
│ GPU secundaria              │
│ Motor de inferencia         │
└─────────────────────────────┘
```

La arquitectura busca que una máquina secundaria pueda actuar como nodo de inferencia sin requerir que el modelo se ejecute directamente en la GPU principal.

---

# Estado del proyecto

**Versión:** v0.2 — Router instrumentado y basado en políticas
**Estado:** Experimental / desarrollo activo

El proyecto se encuentra en una etapa de consolidación. La prioridad actual no es añadir más funcionalidades, sino convertir las capacidades existentes en una arquitectura modular, observable y reproducible.

## Estado por categoría

### DEMOSTRADO

Las siguientes capacidades han sido probadas experimentalmente:

* Inferencia mediante un nodo secundario conectado por LAN.
* Comunicación entre máquina principal y nodo secundario.
* Ejecución de modelos en hardware secundario.
* Medición de tokens/s.
* Medición de VRAM.
* Medición de temperatura.
* Pruebas de concurrencia.
* Enrutamiento entre nodo local y nodo secundario.
* Ejecución de prompts de distinto tamaño.
* Experimento de RPC con división del modelo entre GPUs.
* Comparación de rendimiento entre ejecución distribuida y ejecución desacoplada.

Los resultados corresponden a los escenarios y hardware descritos en este repositorio.

### EXPERIMENTAL

Actualmente se encuentran en desarrollo o validación:

* Política de selección de backend.
* Telemetría estructurada por petición.
* Health checks de nodos.
* Fallback automático.
* Benchmark reproducible.
* Routing basado en estado de recursos.
* Gestión explícita de estados `ONLINE`, `BUSY`, `DEGRADED` y `OFFLINE`.

### FUTURO

Se consideran posibles extensiones:

* Detección del uso de Unity.
* Routing basado en carga real de la estación de trabajo.
* Optimización de KV cache.
* RAG local.
* Integración con servicios cloud.
* Selección automática de modelos.
* Políticas basadas en coste.
* Integración experimental con Barto Compute Economics.
* Optimización de red y migración a Gigabit cuando resulte necesario.

Estas funciones no forman parte de las capacidades demostradas actualmente.

---

# 1. Motivación

Una GPU de escritorio puede ser suficiente para ejecutar modelos pequeños, pero en una estación de desarrollo también puede estar siendo utilizada simultáneamente por:

* Unity;
* IDE;
* navegador;
* herramientas gráficas;
* procesos del sistema;
* aplicaciones de creación de contenido.

Esto puede hacer que ejecutar inferencia local directamente en la GPU principal resulte inconveniente.

Barto Router explora una alternativa:

> utilizar hardware secundario disponible en la red local como nodo de inferencia.

La intención no es necesariamente obtener más rendimiento bruto, sino **separar cargas de trabajo y utilizar el recurso más apropiado para cada petición**.

---

# 2. Arquitectura actual

La arquitectura actual utiliza una máquina principal como punto de entrada y un nodo secundario para inferencia.

```text
                    Request
                       │
                       ▼
               ┌───────────────┐
               │ Barto Router  │
               └───────┬───────┘
                       │
                decisión actual
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
        GPU principal       GPU secundaria
             │                   │
             └─────────┬─────────┘
                       ▼
                   Response
```

El proxy local utiliza actualmente:

```text
127.0.0.1:9000
```

para recibir las solicitudes de inferencia.

---

# 3. Routing actual

La primera versión del sistema utiliza una política sencilla basada principalmente en el tamaño de la petición:

```text
prompt corto  → nodo secundario

prompt largo  → nodo local
```

Esta política funciona como una primera aproximación experimental, pero actualmente se encuentra acoplada a la lógica del router.

La versión v0.2 separará explícitamente:

```text
Router
   ↓
Policy
   ↓
Backend
```

Esto permitirá modificar las reglas de decisión sin modificar la infraestructura principal del router.

---

# 4. Arquitectura objetivo v0.2

La arquitectura objetivo es:

```text
                         Request
                            │
                            ▼
                    ┌──────────────┐
                    │    Router    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ PolicyEngine │
                    └──────┬───────┘
                           │
                     backend_name
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          Local        Secondary       Cloud
             │             │             │
             └─────────────┼─────────────┘
                           │
                           ▼
                      Telemetry
```

El router será responsable de transportar y coordinar solicitudes.

La policy será responsable de decidir dónde conviene ejecutarlas.

Los backends serán responsables de ejecutar la inferencia.

La telemetría registrará qué decisión se tomó y qué ocurrió realmente.

---

# 5. Policy Engine

La política tendrá una interfaz estable desde el comienzo:

```python
decision = policy.decide(request, node_states)
```

Conceptualmente:

```python
class Policy:
    def decide(self, request, node_states):
        ...
```

La primera implementación puede ser deliberadamente sencilla:

```text
policy_v0
→ tamaño del prompt
```

Posteriormente podrán evaluarse otras políticas:

```text
policy_v1
→ prompt + VRAM

policy_v2
→ prompt + VRAM + carga

policy_v3
→ latencia + recursos + coste
```

El objetivo es que `router.py` no tenga que modificarse cada vez que cambia la estrategia de selección.

---

# 6. Telemetría

Una prioridad de v0.2 es convertir cada ejecución en un registro medible.

Cada petición debería registrar, como mínimo:

```text
request_id
timestamp

backend_selected
backend_executed
model

input_tokens
output_tokens

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

La distinción entre:

```text
backend_selected
```

y:

```text
backend_executed
```

es importante.

Por ejemplo:

```text
Policy:
secondary

Secondary:
offline

Fallback:
local
```

El sistema debe permitir reconstruir posteriormente esa secuencia.

---

# 7. Estado de los nodos

Los nodos deberán evolucionar hacia estados explícitos:

```text
ONLINE
BUSY
DEGRADED
OFFLINE
```

El estado observado en el momento de la decisión debe almacenarse como:

```text
node_state_at_request
```

Esto permite distinguir entre:

* una mala decisión de la policy;
* un cambio de estado posterior;
* un fallo de infraestructura;
* un timeout;
* una recuperación mediante fallback.

---

# 8. Fallback

Una función fundamental del router será continuar funcionando cuando el backend seleccionado no esté disponible.

Ejemplo:

```text
SECONDARY ONLINE
        │
        ▼
   ejecutar allí
```

Si está ocupado:

```text
SECONDARY BUSY
        │
        ▼
     fallback
        │
        ▼
       LOCAL
```

Si está desconectado:

```text
SECONDARY OFFLINE
        │
        ▼
     fallback
```

Si se produce timeout:

```text
TIMEOUT
   │
   ▼
fallback
```

La recuperación del nodo deberá permitir que vuelva a participar posteriormente en el routing.

---

# 9. Benchmark reproducible

La siguiente etapa experimental incorporará un benchmark reproducible.

Las pruebas deberían incluir al menos:

### Small

Prompts pequeños.

### Medium

Contextos de tamaño intermedio.

### Large

Contextos grandes.

### Concurrent

Múltiples solicitudes simultáneas.

### Resource pressure

Ejecución mientras la estación principal tiene otros procesos activos.

### Failure

Nodo secundario desconectado o no disponible.

### Recovery

Nodo secundario vuelve a estar disponible.

El objetivo no será solamente medir tokens/s.

También se medirán:

* latencia;
* TTFT;
* throughput;
* VRAM;
* RAM;
* errores;
* fallback;
* disponibilidad.

---

# 10. Experimento de RPC distribuido

Durante la investigación inicial se evaluó una arquitectura donde partes del modelo se ejecutaban en GPUs diferentes mediante RPC.

El resultado experimental mostró una penalización significativa frente a la ejecución desacoplada mediante un nodo remoto.

Por este motivo, la estrategia de dividir directamente el modelo entre las GPUs no constituye actualmente la arquitectura principal del proyecto.

La conclusión experimental es:

> bajo las condiciones evaluadas, utilizar el nodo secundario como servidor de inferencia independiente resulta más conveniente que dividir el modelo entre GPUs mediante RPC.

Este resultado se conserva como evidencia experimental y como criterio para futuras decisiones arquitectónicas.

---

# 11. Resultados experimentales

Las pruebas realizadas hasta ahora han incluido mediciones de:

* tokens por segundo;
* VRAM;
* temperatura;
* concurrencia;
* rendimiento de diferentes hardware;
* ejecución local;
* ejecución remota;
* comportamiento del proxy;
* comunicación LAN.

Los resultados deben interpretarse siempre dentro de las condiciones concretas de hardware, modelo, configuración y carga utilizadas en cada prueba.

No se consideran pruebas universales de rendimiento.

---

# 12. Privacidad y red

En la configuración local validada, las solicitudes pueden permanecer dentro de la red local entre la máquina principal y el nodo secundario.

Esto permite evitar enviar necesariamente las solicitudes a servicios externos.

Sin embargo, esta propiedad depende de la configuración de red utilizada.

Por ello, el proyecto no considera actualmente apropiado afirmar "privacidad absoluta".

La descripción correcta es:

> **el tráfico puede mantenerse dentro de la red local en la configuración experimental utilizada.**

La autenticación y protección de los endpoints forman parte de las futuras mejoras de infraestructura.

---

# 13. Seguridad

La arquitectura actual está pensada principalmente para experimentación en una red local controlada.

A medida que el proyecto evolucione deberán incorporarse:

* autenticación entre nodos;
* identificación de nodos;
* tokens o claves compartidas;
* timeouts;
* validación de mensajes;
* control de clientes;
* logs de eventos;
* manejo explícito de errores.

No se debe asumir que una LAN es automáticamente un entorno seguro.

---

# 14. Principios del proyecto

Barto Router sigue varios principios:

### Evidencia antes que expansión

Una nueva capacidad debe validarse antes de convertirse en una afirmación del sistema.

### Medir antes de optimizar

Primero se establece una línea base y después se modifica la política.

### Separación de responsabilidades

El router no debería contener directamente las reglas de decisión.

### Fallos explícitos

Los errores y fallbacks deben quedar registrados.

### Resultados reproducibles

Los benchmarks deben poder repetirse bajo condiciones conocidas.

### No sobreafirmar

Los resultados se describen según lo que realmente demuestran las pruebas.

---

# 15. Roadmap

## v0.2 — Consolidación

* [ ] Revisar y corregir README.
* [ ] Separar `Router` y `PolicyEngine`.
* [ ] Definir interfaz estable de policy.
* [ ] Implementar telemetría estructurada.
* [ ] Registrar estado del nodo en cada decisión.
* [ ] Separar backend seleccionado de backend ejecutado.
* [ ] Implementar health checks.
* [ ] Implementar fallback.
* [ ] Crear benchmark reproducible.

## v0.3 — Routing adaptativo

Después de obtener suficientes datos:

* [ ] Routing basado en VRAM.
* [ ] Routing basado en carga.
* [ ] Routing basado en latencia.
* [ ] Comparación formal de policies.
* [ ] Persistencia histórica de métricas.

## v0.4 — Optimización

Posibles extensiones:

* [ ] Detección de procesos de desarrollo.
* [ ] Detección del estado de Unity.
* [ ] Optimización de KV cache.
* [ ] RAG local.
* [ ] Mejoras de red.

## Futuro

Posibles extensiones de investigación:

* [ ] Selección automática de modelos.
* [ ] Cloud fallback.
* [ ] Routing basado en coste.
* [ ] Predicción de latencia.
* [ ] Políticas económicas.
* [ ] Integración experimental con Barto Compute Economics.

---

# 16. Relación con Barto Compute Economics

Barto Router y Barto Compute Economics son proyectos relacionados pero independientes.

### Barto Router

Se ocupa de:

> **dónde y cómo ejecutar una petición.**

### Barto Compute Economics

Explora:

> **cómo evaluar económicamente la conveniencia de distintas decisiones de cómputo.**

La integración futura podría producir:

```text
Request
   ↓
Barto Router
   ↓
Policy Engine
   ↓
Economic Policy
   ↓
Backend
```

Pero el router debe seguir funcionando con políticas simples sin depender de Barto Compute Economics.

---

# 17. Criterio de éxito de v0.2

La versión v0.2 se considerará consolidada cuando sea posible responder, para cualquier petición:

1. ¿Qué backend estaba disponible?
2. ¿Qué estado tenía?
3. ¿Qué decidió la policy?
4. ¿Dónde terminó ejecutándose?
5. ¿Hubo fallback?
6. ¿Cuánto tardó?
7. ¿Cuánta VRAM/RAM utilizó?
8. ¿La petición terminó correctamente?

El objetivo no es todavía tener la política óptima.

El objetivo es conseguir un sistema donde las decisiones sean:

**observables, reproducibles y comparables.**

---

# 18. Objetivo a largo plazo

La evolución buscada es pasar progresivamente de:

```text
"envío una petición a otra máquina"
```

a:

```text
"el sistema determina dónde conviene ejecutar
la petición utilizando el estado real de los recursos,
ejecuta la decisión y registra evidencia de lo ocurrido."
```

Ese cambio constituye el principal objetivo técnico de las siguientes versiones.

---

# Licencia

Consultar los archivos de licencia del repositorio para conocer las condiciones actuales de uso y distribución.
