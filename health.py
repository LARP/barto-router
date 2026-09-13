import time
import threading
import urllib.request
from typing import Dict
from policy import BackendNode, NodeStatus

class HealthMonitor:
    """
    Monitor proactivo de salud y latencia en segundo plano (Heartbeat).
    Sondea periódicamente los backends y actualiza su estado (ONLINE, BUSY, OFFLINE)
    para permitir decisiones y fallbacks preventivos en el PolicyEngine.
    """
    def __init__(self, backends: Dict[str, BackendNode], interval_seconds: float = 5.0, timeout: float = 0.8):
        self.backends = backends
        self.interval = interval_seconds
        self.timeout = timeout
        self.running = False
        self.thread: threading.Thread = None
        self.failure_counts: Dict[str, int] = {k: 0 for k in backends.keys()}

    def check_node(self, node: BackendNode):
        url = f"{node.base_url}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "barto-router-health"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.time() - t0) * 1000
                node.last_latency_ms = round(elapsed_ms, 2)
                node.last_check = time.strftime("%Y-%m-%d %H:%M:%S")
                self.failure_counts[node.name] = 0
                
                if resp.status == 200:
                    if node.status != NodeStatus.ONLINE:
                        print(f"[HealthMonitor] [RESTORE] Nodo '{node.name}' volvió a estar ONLINE ({elapsed_ms:.1f}ms)")
                    node.status = NodeStatus.ONLINE
                elif resp.status == 503:
                    node.status = NodeStatus.BUSY
                else:
                    node.status = NodeStatus.DEGRADED
        except Exception as e:
            self.failure_counts[node.name] = self.failure_counts.get(node.name, 0) + 1
            node.last_check = time.strftime("%Y-%m-%d %H:%M:%S")
            # Tras 2 fallos consecutivos, marcar formalmente OFFLINE
            if self.failure_counts[node.name] >= 2:
                if node.status != NodeStatus.OFFLINE:
                    print(f"[HealthMonitor] [ALERTA] Nodo '{node.name}' no responde tras {self.failure_counts[node.name]} intentos -> Marcado OFFLINE ({e})")
                node.status = NodeStatus.OFFLINE
            else:
                node.status = NodeStatus.DEGRADED

    def check_all_sync(self):
        """Ejecuta una ronda síncrona de comprobación (ideal al arrancar)."""
        threads = []
        for node in self.backends.values():
            t = threading.Thread(target=self.check_node, args=(node,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=self.timeout + 0.2)

    def _monitor_loop(self):
        while self.running:
            for node in list(self.backends.values()):
                self.check_node(node)
            time.sleep(self.interval)

    def start(self):
        if not self.running:
            self.running = True
            # Comprobación inicial inmediata
            self.check_all_sync()
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            print(f"[HealthMonitor] Monitor de salud iniciado (intervalo: {self.interval}s, timeout: {self.timeout}s)")

    def stop(self):
        self.running = False
