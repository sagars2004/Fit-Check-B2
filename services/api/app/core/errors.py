from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FitCheckError(Exception):
    code: str
    message: str
    retryable: bool = False
    entity_id: str | None = None
    recommended_action: str | None = None
    correlation_id: str | None = None

    def as_dict(self) -> dict[str, object | None]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "entity_id": self.entity_id,
            "recommended_action": self.recommended_action,
            "correlation_id": self.correlation_id,
        }

