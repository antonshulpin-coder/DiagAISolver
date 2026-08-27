from dataclasses import dataclass, field


@dataclass
class AIResponse:
    """Стандартный ответ AI-провайдера."""
    success: bool
    content: str
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    error: str | None = None
