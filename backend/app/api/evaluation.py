from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from app.schemas.request import EvaluationRequest
from app.schemas.response import EvaluationReportResponse
from app.evaluation.evaluate import evaluation_pipeline
from app.core.logging_config import SafeLogger
from app.db.database import db

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.post("/run", response_model=EvaluationReportResponse)
def run_evaluation_suite(req: EvaluationRequest = EvaluationRequest()) -> EvaluationReportResponse:
    """Executes evaluation pipeline on specified or official benchmark questions."""
    try:
        report = evaluation_pipeline.run_evaluation(
            dataset_name=req.dataset_name,
            max_questions=req.max_questions,
            dry_run=req.dry_run
        )
        return report
    except Exception as e:
        SafeLogger.error(f"Error during evaluation execution: {str(e)}")
        raise HTTPException(status_code=500, detail="Evaluation execution encountered an internal error.")

@router.get("/latest")
def get_latest_evaluation() -> Optional[Dict[str, Any]]:
    """Returns the most recent persisted evaluation run."""
    run = db.get_latest_evaluation_run()
    if not run:
        return {
            "status": "not_evaluated",
            "message": "No evaluation run recorded yet. Please run evaluation from the owner dashboard."
        }
    return run
