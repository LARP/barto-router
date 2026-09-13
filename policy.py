import subprocess
import time
from typing import Dict, Tuple, Any

class NodeStatus:
    ONLINE = "ONLINE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"

class BackendNode:
    def __init__(self, name: str, base_url: str, is_local: bool = False):
        self.name = name
        self.base_url = base_url
        self.is_local = is_local
        self.status = NodeStatus.ONLINE
        self.last_latency_ms: float = 0.0
        self.last_check: str = time.strftime("%Y-%m-%d %H:%M:%S")

    def __repr__(self):
        return f"<BackendNode {self.name} [{self.status}] @ {self.base_url} ({self.last_latency_ms}ms)>"

class BasePolicy:
    """
    Interfaz abstracta de política de decisión de routing.
    Permite evaluar dónde ejecutar una petición a partir de los datos
    de la solicitud y el estado de los nodos disponibles.
    """
    def __init__(self, name: str = "BasePolicy"):
        self.name = name

    def decide(self, request_data: dict, backends: Dict[str, BackendNode]) -> Tuple[str, str]:
        """
        Retorna una tupla: (backend_name_seleccionado, razon_de_la_decision)
        """
        raise NotImplementedError("Las subclases deben implementar el método decide().")

class ThresholdPolicy(BasePolicy):
    """
    Política v0.2 con Conciencia de Salud (Health-Aware):
    Enrutamiento basado en umbral de tamaño de prompt, disponibilidad de la GPU local
    y estado preventivo de los nodos (ONLINE, BUSY, OFFLINE).
    """
    def __init__(
        self,
        max_prompt_chars_for_secondary: int = 3000,
        max_gpu_util_for_local: int = 15,
        min_vram_free_mb_for_local: int = 3000
    ):
        super().__init__(name="ThresholdPolicy_v0.2")
        self.max_prompt_chars = max_prompt_chars_for_secondary
        self.max_gpu_util = max_gpu_util_for_local
        self.min_vram_free_mb = min_vram_free_mb_for_local

    def _is_local_gpu_available(self) -> Tuple[bool, str]:
        try:
            cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.free", "--format=csv,noheader,nounits"]
            output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
            util_str, free_mem_str = output.split(",")
            gpu_util = int(util_str.strip())
            free_mem = int(free_mem_str.strip())
            
            if gpu_util >= self.max_gpu_util:
                return False, f"GPU util alta ({gpu_util}% >= {self.max_gpu_util}%)"
            if free_mem <= self.min_vram_free_mb:
                return False, f"VRAM libre insuficiente ({free_mem}MB <= {self.min_vram_free_mb}MB)"
            
            return True, f"GPU idle ({gpu_util}%, {free_mem}MB VRAM libre)"
        except Exception as e:
            return False, f"Error consultando nvidia-smi: {e}"

    def decide(self, request_data: dict, backends: Dict[str, BackendNode]) -> Tuple[str, str]:
        messages = request_data.get("messages", [])
        total_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))

        nodo_sec = backends.get("NODO_SECUNDARIO")
        nodo_local = backends.get("LOCAL_RTX")

        sec_is_online = nodo_sec and nodo_sec.status in [NodeStatus.ONLINE, NodeStatus.BUSY]
        local_is_online = nodo_local and nodo_local.status == NodeStatus.ONLINE

        # 1. Caso crítico preventivo: Si el nodo secundario está OFFLINE
        if not sec_is_online:
            if local_is_online:
                return "LOCAL_RTX", f"Fallback Preventivo: NODO_SECUNDARIO está {nodo_sec.status if nodo_sec else 'DESCONOCIDO'}"
            else:
                return "NODO_SECUNDARIO", "Todos los backends están degradados/offline; reintentando por secundario"

        # 2. Si el prompt supera el umbral de carga pesada:
        if total_chars > self.max_prompt_chars:
            if local_is_online:
                available, reason = self._is_local_gpu_available()
                if available:
                    return "LOCAL_RTX", f"Prompt extenso ({total_chars} chars > {self.max_prompt_chars}) y {reason}"
                else:
                    return "NODO_SECUNDARIO", f"Prompt extenso ({total_chars} chars) pero estación ocupada ({reason})"
            return "NODO_SECUNDARIO", f"Prompt extenso ({total_chars} chars) pero LOCAL_RTX no disponible (status={nodo_local.status if nodo_local else 'N/A'})"

        # 3. Por defecto: Proteger la estación de trabajo y enviar al nodo secundario
        latency_info = f" ({nodo_sec.last_latency_ms}ms)" if nodo_sec.last_latency_ms > 0 else ""
        return "NODO_SECUNDARIO", f"Carga ligera ({total_chars} chars <= {self.max_prompt_chars}) -> Proteccion GPU Principal{latency_info}"

class PolicyEngine:
    """
    Orquestador de políticas, estado de backends y monitor de salud.
    """
    def __init__(self, default_policy: BasePolicy = None, enable_health_monitor: bool = True):
        self.backends: Dict[str, BackendNode] = {
            "NODO_SECUNDARIO": BackendNode("NODO_SECUNDARIO", "http://192.168.100.105:8080"),
            "LOCAL_RTX": BackendNode("LOCAL_RTX", "http://127.0.0.1:8081", is_local=True)
        }
        self.policy = default_policy or ThresholdPolicy()
        self.health_monitor = None
        
        if enable_health_monitor:
            from health import HealthMonitor
            self.health_monitor = HealthMonitor(self.backends, interval_seconds=5.0)
            self.health_monitor.start()

    def set_policy(self, policy: BasePolicy):
        self.policy = policy

    def get_backend(self, name: str) -> BackendNode:
        return self.backends.get(name)

    def decide(self, request_data: dict) -> Tuple[BackendNode, str]:
        backend_name, reason = self.policy.decide(request_data, self.backends)
        selected_backend = self.backends.get(backend_name)
        if not selected_backend:
            selected_backend = self.backends["NODO_SECUNDARIO"]
            reason += " (Fallback por backend desconocido)"
        return selected_backend, reason

    def get_status_summary(self) -> dict:
        return {
            "policy": self.policy.name,
            "backends": {
                k: {
                    "status": v.status,
                    "url": v.base_url,
                    "latency_ms": v.last_latency_ms,
                    "last_check": v.last_check
                }
                for k, v in self.backends.items()
            }
        }
