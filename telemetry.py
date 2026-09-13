import json
import time
import os
from typing import Dict, Any, Optional

TELEMETRY_LOG_FILE = "telemetry.jsonl"

class TelemetryRecord:
    def __init__(
        self,
        request_id: str,
        policy_name: str,
        decision_backend: str,
        decision_reason: str,
        prompt_chars: int = 0
    ):
        self.request_id = request_id
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.policy_name = policy_name
        self.decision_backend = decision_backend
        self.decision_reason = decision_reason
        self.prompt_chars = prompt_chars
        
        # Campos completados tras la ejecución
        self.execution_backend: str = decision_backend
        self.total_time_ms: float = 0.0
        self.ttft_ms: float = 0.0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.tokens_per_second: float = 0.0
        self.fallback_occurred: bool = False
        self.fallback_reason: Optional[str] = None
        self.success: bool = False
        self.error_message: Optional[str] = None

    def finalize(
        self,
        execution_backend: str,
        total_time_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        error_message: Optional[str] = None,
        fallback_occurred: bool = False,
        fallback_reason: Optional[str] = None
    ):
        self.execution_backend = execution_backend
        self.total_time_ms = round(total_time_ms, 2)
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.success = success
        self.error_message = error_message
        self.fallback_occurred = fallback_occurred
        self.fallback_reason = fallback_reason
        
        if total_time_ms > 0 and completion_tokens > 0:
            self.tokens_per_second = round(completion_tokens / (total_time_ms / 1000.0), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "policy_name": self.policy_name,
            "decision_backend": self.decision_backend,
            "decision_reason": self.decision_reason,
            "execution_backend": self.execution_backend,
            "prompt_chars": self.prompt_chars,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_time_ms": self.total_time_ms,
            "tokens_per_second": self.tokens_per_second,
            "fallback_occurred": self.fallback_occurred,
            "fallback_reason": self.fallback_reason,
            "success": self.success,
            "error_message": self.error_message
        }

class TelemetryLogger:
    def __init__(self, log_path: str = TELEMETRY_LOG_FILE):
        self.log_path = log_path

    def log(self, record: TelemetryRecord):
        data = record.to_dict()
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[TelemetryLogger] Error guardando log: {e}")
