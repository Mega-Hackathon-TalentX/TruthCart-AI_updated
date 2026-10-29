import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from app.core.config import settings
from app.core.logging_config import SafeLogger

class ReportGenerator:
    """Generates and writes machine-readable evaluation reports."""

    @staticmethod
    def save_report(report_data: Dict[str, Any]) -> str:
        report_dir = settings.get_evaluation_report_path()
        report_dir.mkdir(parents=True, exist_ok=True)

        report_id = report_data.get("report_id", str(uuid.uuid4()))
        filename = f"eval_report_{report_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        out_path = report_dir / filename

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
            SafeLogger.info(f"Evaluation report persisted: {filename}")
        except Exception as e:
            SafeLogger.error(f"Error saving evaluation report: {str(e)}")

        return str(out_path)

report_generator = ReportGenerator()
