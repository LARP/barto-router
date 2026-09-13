import subprocess
import time
import json
import os
from typing import Dict, Tuple, Any, Optional

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
    """
    def __init__(self, name: str = "BasePolicy"):
        self.name = name

    def decide(self, request_data: dict, backends: Dict[str, BackendNode]) -> Tuple[str, str]:
        raise NotImplementedError("Las subclases deben implementar el método decide().")

class ThresholdPolicy(BasePolicy):
    """
    Política v0.2 con Conciencia de Salud (Health-Aware) y umbrales fijos.
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

        if not sec_is_online:
            if local_is_online:
                return "LOCAL_RTX", f"Fallback Preventivo: NODO_SECUNDARIO está {nodo_sec.status if nodo_sec else 'DESCONOCIDO'}"
            else:
                return "NODO_SECUNDARIO", "Todos los backends degradados; reintentando secundario"

        if total_chars > self.max_prompt_chars:
            if local_is_online:
                available, reason = self._is_local_gpu_available()
                if available:
                    return "LOCAL_RTX", f"Prompt extenso ({total_chars} chars > {self.max_prompt_chars}) y {reason}"
                else:
                    return "NODO_SECUNDARIO", f"Prompt extenso ({total_chars} chars) pero estación ocupada ({reason})"
            return "NODO_SECUNDARIO", f"Prompt extenso pero LOCAL_RTX no disponible"

        latency_info = f" ({nodo_sec.last_latency_ms}ms)" if nodo_sec.last_latency_ms > 0 else ""
        return "NODO_SECUNDARIO", f"Carga ligera ({total_chars} chars <= {self.max_prompt_chars}) -> Protección GPU Principal{latency_info}"

class CostEstimationPolicy(BasePolicy):
    """
    Etapa 6 y 7: Política de Estimación de Costo Temporal y Conciencia de VRAM (Informe Oficial v0.4).
    
    Fórmula oficial:
    costo_remoto = tokens_estimados / TPS_remoto + TTFT_remoto + latencia_LAN
    costo_local  = tokens_estimados / TPS_local  + TTFT_local
    
    Elegir remoto si:
    costo_remoto < costo_local * PROTECTION_FACTOR
    
    Filtro duro de VRAM (Etapa 7):
    Si VRAM_requerida(peticion) > VRAM_libre_segura_actual -> ejecutar remoto obligatoriamente.
    """
    def __init__(
        self,
        calibration_path: str = "calibration_params.json",
        vram_safety_margin_mb: int = 1500,
        model_vram_requirement_mb: int = 1200
    ):
        super().__init__(name="CostEstimationPolicy_v0.4")
        self.vram_safety_margin_mb = vram_safety_margin_mb
        self.model_vram_requirement_mb = model_vram_requirement_mb
        
        # Parámetros calibrados por defecto (fallback seguro)
        self.tps_remoto = 42.24
        self.ttft_remoto_s = 0.049
        self.lan_latency_s = 0.002
        
        self.tps_local = 89.36
        self.ttft_local_s = 0.025
        self.protection_factor = 2.5 # Factor de protección moderado por P90

        if os.path.exists(calibration_path):
            try:
                with open(calibration_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    m = data.get("metrics", {})
                    self.tps_remoto = m.get("remote", {}).get("tps_p50", self.tps_remoto)
                    self.ttft_remoto_s = m.get("remote", {}).get("ttft_ms_p50", 49.0) / 1000.0
                    self.lan_latency_s = m.get("remote", {}).get("lan_latency_ms", 2.0) / 1000.0

                    self.tps_local = m.get("local", {}).get("tps_p50", self.tps_local)
                    self.ttft_local_s = m.get("local", {}).get("ttft_ms_p50", 25.0) / 1000.0

                    p_fact = data.get("derived_parameters", {}).get("protection_factor")
                    if p_fact:
                        self.protection_factor = min(float(p_fact), 3.0) # Límite superior razonable
            except Exception as e:
                print(f"[CostEstimationPolicy] Advertencia leyendo calibracion: {e}")

    def _get_vram_free_mb(self) -> int:
        try:
            cmd = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"]
            out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
            return int(out.split("\n")[0].strip())
        except Exception:
            return 0

    def estimate_tokens(self, request_data: dict) -> int:
        """Estima los tokens de salida esperado a partir de max_tokens o prompt length."""
        max_tok = request_data.get("max_tokens")
        if max_tok and max_tok > 0:
            return min(int(max_tok), 250)
        messages = request_data.get("messages", [])
        total_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
        return min(max(int(total_chars * 0.5), 40), 200)

    def decide(self, request_data: dict, backends: Dict[str, BackendNode]) -> Tuple[str, str]:
        nodo_sec = backends.get("NODO_SECUNDARIO")
        nodo_local = backends.get("LOCAL_RTX")

        sec_is_online = nodo_sec and nodo_sec.status in [NodeStatus.ONLINE, NodeStatus.BUSY]
        local_is_online = nodo_local and nodo_local.status == NodeStatus.ONLINE

        if not sec_is_online:
            if local_is_online:
                return "LOCAL_RTX", "Fallback Preventivo: NODO_SECUNDARIO Offline/Degradado"
            return "NODO_SECUNDARIO", "Backends degradados; reintento secundario"

        # 1. Filtro Duro de VRAM (Etapa 7)
        vram_free = self._get_vram_free_mb()
        vram_safe_budget = max(0, vram_free - self.vram_safety_margin_mb)
        
        if self.model_vram_requirement_mb > vram_safe_budget:
            return "NODO_SECUNDARIO", (
                f"Filtro VRAM Duro: VRAM segura disponible ({vram_safe_budget}MB) < "
                f"Requerida ({self.model_vram_requirement_mb}MB). Protección GPU principal activa."
            )

        # 2. Modelo de Costo Temporal Estimado (Etapa 6)
        est_tokens = self.estimate_tokens(request_data)
        
        costo_remoto = (est_tokens / self.tps_remoto) + self.ttft_remoto_s + self.lan_latency_s
        costo_local = (est_tokens / self.tps_local) + self.ttft_local_s
        umbral_protegido = costo_local * self.protection_factor

        if costo_remoto < umbral_protegido:
            return "NODO_SECUNDARIO", (
                f"CostPolicy: Costo remoto ({costo_remoto:.2f}s) < Costo local protegido ({umbral_protegido:.2f}s) "
                f"[PF={self.protection_factor}, est_tokens={est_tokens}]"
            )
        else:
            if local_is_online:
                return "LOCAL_RTX", (
                    f"CostPolicy: Ejecución oportunista. Costo local ({costo_local:.2f}s) supera significativamente a remoto "
                    f"({costo_remoto:.2f}s) con VRAM segura libre ({vram_free}MB)"
                )
            return "NODO_SECUNDARIO", "CostPolicy prefería local pero LOCAL_RTX no disponible"

class PolicyEngine:
    """
    Orquestador de políticas, estado de backends y monitor de salud.
    """
    def __init__(self, default_policy: BasePolicy = None, enable_health_monitor: bool = True):
        self.backends: Dict[str, BackendNode] = {
            "NODO_SECUNDARIO": BackendNode("NODO_SECUNDARIO", "http://192.168.100.105:8080"),
            "LOCAL_RTX": BackendNode("LOCAL_RTX", "http://127.0.0.1:8081", is_local=True)
        }
        self.policy = default_policy or CostEstimationPolicy()
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
