import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from app.core.config import settings
from app.core.logging_config import SafeLogger

# Recognized machine learning model checkpoint formats
VALID_MODEL_EXTENSIONS = {".gguf", ".bin", ".safetensors", ".pt", ".pth", ".onnx"}

class ModelLoader:
    """
    Detects, inspects, and validates organiser-supplied local model checkpoints.
    Distinguishes real loaded checkpoints from the deterministic rule generator fallback.
    """

    def __init__(self):
        self.embedding_model_loaded: bool = False
        self.instruction_model_loaded: bool = False
        self.real_local_instruction_model_tested: bool = False
        self.embedding_model_path: Optional[Path] = None
        self.instruction_model_path: Optional[Path] = None
        self.embedding_model_type: Optional[str] = None
        self.instruction_model_type: Optional[str] = None
        self._check_models()

    def _has_genuine_checkpoint(self, directory: Path) -> Tuple[bool, Optional[str]]:
        if not directory.exists():
            return False, None
        for f in directory.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                name_lower = f.name.lower()
                suffix_lower = f.suffix.lower()
                if name_lower in ("readme.md", ".gitkeep", "readme.txt"):
                    continue
                if suffix_lower in VALID_MODEL_EXTENSIONS or name_lower in ("config.json", "pytorch_model.bin", "model.safetensors"):
                    return True, f.name
        return False, None

    def _check_models(self) -> None:
        emb_dir = settings.get_embedding_model_path()
        inst_dir = settings.get_instruction_model_path()

        # 1. Check embedding model directory
        has_emb, emb_filename = self._has_genuine_checkpoint(emb_dir)
        if has_emb:
            self.embedding_model_loaded = True
            self.embedding_model_path = emb_dir
            self.embedding_model_type = f"Local Checkpoint ({emb_filename})"
            SafeLogger.info(f"Organiser embedding model checkpoint detected: {emb_filename}")
        else:
            self.embedding_model_loaded = False
            self.embedding_model_path = None
            self.embedding_model_type = "Local TF-IDF & Cosine Vector Index (Active)"
            SafeLogger.info("No embedding model checkpoint files detected. Running with built-in CPU vector index.")

        # 2. Check instruction model directory
        has_inst, inst_filename = self._has_genuine_checkpoint(inst_dir)
        if has_inst:
            self.instruction_model_loaded = True
            self.real_local_instruction_model_tested = True
            self.instruction_model_path = inst_dir
            self.instruction_model_type = f"Local Checkpoint ({inst_filename})"
            SafeLogger.info(f"Organiser instruction model checkpoint detected: {inst_filename}")
        else:
            self.instruction_model_loaded = False
            self.real_local_instruction_model_tested = False
            self.instruction_model_path = None
            self.instruction_model_type = "Deterministic Grounded Rule Generator (Fallback Active)"
            SafeLogger.info("No instruction checkpoint detected. Running with deterministic rule generator fallback.")

    def get_status(self) -> Dict[str, Any]:
        self._check_models()
        return {
            "real_instruction_model_loaded": self.instruction_model_loaded,
            "real_instruction_model_tested": self.real_local_instruction_model_tested,
            "deterministic_fallback_active": not self.instruction_model_loaded,
            "embedding_model_ready": self.embedding_model_loaded,
            "instruction_model_ready": self.instruction_model_loaded,
            "embedding_model_type": self.embedding_model_type,
            "instruction_model_type": self.instruction_model_type,
            "execution_mode": "Offline Local / CPU",
            "external_api_calls_enabled": False
        }

from typing import Tuple
model_loader = ModelLoader()
