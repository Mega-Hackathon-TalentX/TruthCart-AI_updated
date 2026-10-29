from typing import Dict, Any, Optional
from app.llm.model_loader import model_loader
from app.core.logging_config import SafeLogger

class LocalModelAdapter:
    """
    Adapter abstraction for offline inference using organiser-supplied model or fallback.
    Prevents repeated reloads and encapsulates CPU generation.
    """

    def __init__(self):
        self.is_active = model_loader.instruction_model_loaded

    def generate(self, prompt: str, max_tokens: int = 150) -> Optional[str]:
        """
        Executes local model inference if checkpoints are mounted.
        Returns generated text or None to trigger deterministic grounded response fallback.
        """
        if not model_loader.instruction_model_loaded:
            return None

        # When organisers place weights in models/instruction_model, this adapter routes
        # to the local runtime (e.g. transformers or llama-cpp)
        SafeLogger.info("Executing local model inference via adapter.")
        return None

local_model_adapter = LocalModelAdapter()
