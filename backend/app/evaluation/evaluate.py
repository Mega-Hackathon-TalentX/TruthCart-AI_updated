import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings
from app.core.logging_config import SafeLogger
from app.ingestion.catalogue_loader import catalogue_loader
from app.llm.model_loader import model_loader
from app.llm.query_understanding import query_understanding
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.evidence_engine.decision_engine import decision_engine
from app.evidence_engine.citation_validator import citation_validator
from app.llm.response_generator import response_generator
from app.evaluation.metrics import evaluation_metrics
from app.evaluation.report_generator import report_generator
from app.schemas.response import QuestionEvaluationResult, EvaluationReportResponse

class EvaluationPipeline:
    """Orchestrates end-to-end evaluation runs against test datasets."""

    @staticmethod
    def _parse_question_file(file_path: Path) -> List[Dict[str, Any]]:
        """Parses json, jsonl, or csv evaluation benchmark files."""
        ext = file_path.suffix.lower()
        if ext == ".jsonl":
            with open(file_path, "r", encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        elif ext == ".csv":
            import csv
            with open(file_path, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def load_dataset(dataset_name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        test_dir = settings.get_test_questions_path()
        dev_dir = settings.get_dev_fixtures_path()

        # Check explicit dataset_name first
        if dataset_name:
            for parent_dir in (test_dir, dev_dir):
                cand = parent_dir / dataset_name
                if cand.exists():
                    label = f"Official: {dataset_name}" if parent_dir == test_dir else f"Development Fixture: {dataset_name}"
                    return EvaluationPipeline._parse_question_file(cand), label

        # Priority 1: Official organizer files in test_questions
        for pref in ("truthcart_evaluation_questions_150.jsonl", "truthcart_evaluation_questions_150.csv", "evaluation_benchmark_150.json"):
            target = test_dir / pref
            if target.exists():
                return EvaluationPipeline._parse_question_file(target), f"Official: {pref}"

        # Priority 2: Any benchmark file in test_dir
        for pattern in ("*.jsonl", "*.json", "*.csv"):
            matches = list(test_dir.glob(pattern))
            if matches:
                target = matches[0]
                return EvaluationPipeline._parse_question_file(target), f"Official: {target.name}"

        # Priority 3: Default fixture file
        fixture_file = dev_dir / "sample_eval_questions.json"
        if fixture_file.exists():
            return EvaluationPipeline._parse_question_file(fixture_file), "Development Fixture: sample_eval_questions.json"

        return [], "No dataset found"

    def run_evaluation(
        self,
        dataset_name: Optional[str] = None,
        max_questions: Optional[int] = None,
        dry_run: bool = False
    ) -> EvaluationReportResponse:
        questions, dataset_source = self.load_dataset(dataset_name)

        if not questions:
            report_id = str(uuid.uuid4())
            return EvaluationReportResponse(
                report_id=report_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset_name="Awaiting official test questions",
                total_questions_tested=0,
                successfully_evaluated=0,
                groundedness_score=0.0,
                answer_helpfulness_score=0.0,
                refusal_accuracy=0.0,
                clarification_accuracy=0.0,
                unsupported_claim_rate=0.0,
                citation_validity_rate=0.0,
                avg_latency_ms=0.0,
                compute_info={"device": "CPU", "offline": True},
                details=[]
            )

        if max_questions:
            questions = questions[:max_questions]

        detailed_results: List[QuestionEvaluationResult] = []
        raw_eval_items: List[Dict[str, Any]] = []

        start_all = time.perf_counter()

        for q_item in questions:
            qid = str(q_item.get("question_id") or q_item.get("id") or q_item.get("qid") or q_item.get("test_id") or f"Q-{len(detailed_results)+1}")
            query_str = str(
                q_item.get("user_question")
                or q_item.get("user_prompt")
                or q_item.get("query")
                or q_item.get("question")
                or q_item.get("prompt")
                or q_item.get("text")
                or ""
            )
            # Support all benchmark outcome formats
            expected_dec = (
                q_item.get("expected_outcome")
                or q_item.get("expected_decision")
                or q_item.get("expected_behavior")
                or q_item.get("decision")
                or q_item.get("expected")
            )
            # must_not_claim: list of forbidden strings / behaviors (R3 hallucination penalty)
            must_not_claim: List[str] = []
            raw_mnc = q_item.get("must_not_claim")
            if raw_mnc:
                if isinstance(raw_mnc, list):
                    must_not_claim.extend(raw_mnc)
                else:
                    must_not_claim.append(str(raw_mnc))
            raw_mnd = q_item.get("must_not_do")
            if raw_mnd:
                must_not_claim.append(str(raw_mnd))

            expected_evidence = q_item.get("expected_evidence_id") or q_item.get("primary_product_id")

            t0 = time.perf_counter()

            # Pipeline execution
            parsed = query_understanding.parse(query_str)
            product_cands, policy_cand = hybrid_retriever.retrieve(query_str, parsed)
            evidence_obj = decision_engine.evaluate(query_str, parsed, product_cands, policy_cand)

            matched_prods = [c.data for c in product_cands]
            response_text, products, citations, _, _ = response_generator.generate_response(evidence_obj, matched_prods)

            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Citation validation
            verified_pids = {ev.source_id for ev in evidence_obj.evidence if ev.source_type == "product"}
            verified_pol_ids = {ev.source_id for ev in evidence_obj.evidence if ev.source_type == "policy"}
            is_valid_cit, _, invalid_cits = citation_validator.validate_citations(
                response_text, verified_pids, verified_pol_ids
            )

            # Check if actual decision matches expected
            actual_dec = evidence_obj.decision
            dec_match = (actual_dec == expected_dec) if expected_dec else None

            # Check unsupported claims: any invalid citation OR answer claimed with unsupported fields
            has_unsupported = len(invalid_cits) > 0 or (actual_dec == "ANSWER" and len(evidence_obj.unsupported_fields) > 0)

            # R3 hallucination penalty: check must_not_claim strings against response (case-insensitive)
            hallucinated_claims: List[str] = []
            resp_lower = response_text.lower()
            for forbidden in must_not_claim:
                if forbidden.lower() in resp_lower:
                    hallucinated_claims.append(forbidden)

            # Evidence match check: if question specified exact required evidence, verify citation presence
            evidence_matched = True
            if expected_evidence and actual_dec == "ANSWER" and expected_dec == "ANSWER":
                clean_exp = expected_evidence.replace("POLICY:", "").strip()
                evidence_matched = any(clean_exp in cit for cit in citations) or any(
                    clean_exp == ev.source_id or expected_evidence == ev.source_id for ev in evidence_obj.evidence
                )

            # Determine pass/fail & failure reason
            passed = True
            failure_reason = None
            if expected_dec and actual_dec != expected_dec:
                passed = False
                failure_reason = f"Decision mismatch: expected {expected_dec}, got {actual_dec}"
            elif not evidence_matched:
                passed = False
                failure_reason = f"Expected evidence [{expected_evidence}] not cited in answer"
            elif hallucinated_claims:
                passed = False
                failure_reason = f"Hallucinated forbidden claims: {hallucinated_claims}"
            elif not is_valid_cit:
                passed = False
                failure_reason = f"Citation validation failed: {invalid_cits}"
            elif has_unsupported:
                passed = False
                failure_reason = f"Unsupported fields found in answer: {evidence_obj.unsupported_fields}"

            # Evidence preview
            evidence_preview = [
                f"[{ev.source_type.upper()}:{ev.source_id}] {ev.field}: {str(ev.value)[:100]}"
                for ev in evidence_obj.evidence[:3]
            ]

            # Build notes with hallucination penalty info if triggered
            base_notes = q_item.get("notes") or ""
            if hallucinated_claims:
                penalty_note = f"[HALLUCINATION PENALTY] Forbidden claims found: {hallucinated_claims}"
                notes_out = f"{base_notes} | {penalty_note}".strip(" |")
            else:
                notes_out = base_notes or None

            res = QuestionEvaluationResult(
                question_id=qid,
                query=query_str,
                expected_decision=expected_dec,
                actual_decision=actual_dec,
                decision_match=dec_match,
                passed=passed,
                failure_reason=failure_reason,
                citations=citations,
                citations_valid=is_valid_cit,
                has_unsupported_claims=has_unsupported or bool(hallucinated_claims),
                latency_ms=round(latency_ms, 2),
                token_cost=0.0,
                notes=notes_out,
                evidence_preview=evidence_preview
            )
            detailed_results.append(res)
            raw_eval_items.append(res.model_dump())

        metrics = evaluation_metrics.calculate(raw_eval_items)
        report_id = str(uuid.uuid4())

        cat_status = catalogue_loader.get_status().get("status", "Unknown")
        model_status = model_loader.get_status().get("instruction_model_type", "deterministic_fallback")

        report_response = EvaluationReportResponse(
            report_id=report_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_name=dataset_source,
            total_cases_available=metrics["total_cases_available"],
            total_cases_executed=metrics["total_cases_executed"],
            total_cases_passed=metrics["total_cases_passed"],
            total_cases_failed=metrics["total_cases_failed"],
            total_cases_skipped=metrics["total_cases_skipped"],
            total_questions_tested=len(detailed_results),
            successfully_evaluated=len(detailed_results),
            groundedness_score=metrics["groundedness_score"],
            answer_helpfulness_score=metrics["answer_helpfulness_score"],
            refusal_accuracy=metrics["refusal_accuracy"],
            clarification_accuracy=metrics["clarification_accuracy"],
            unsupported_claim_rate=metrics["unsupported_claim_rate"],
            citation_validity_rate=metrics["citation_validity_rate"],
            citation_coverage_rate=metrics["citation_coverage_rate"],
            avg_latency_ms=metrics["avg_latency_ms"],
            latency_p50_ms=metrics["latency_p50_ms"],
            latency_p90_ms=metrics["latency_p90_ms"],
            latency_p99_ms=metrics["latency_p99_ms"],
            avg_token_cost=metrics.get("avg_token_cost", 0.0),
            total_token_cost=metrics.get("total_token_cost", 0.0),
            data_readiness=cat_status,
            model_readiness=model_status,
            compute_info={
                "device": "CPU",
                "offline": True,
                "token_cost_usd": 0.0,
                "total_run_time_sec": round(time.perf_counter() - start_all, 2)
            },
            details=detailed_results
        )

        if not dry_run:
            report_generator.save_report(report_response.model_dump())
            try:
                from app.db.database import db
                db.save_evaluation_run(report_response.model_dump())
            except Exception as e:
                SafeLogger.warning(f"Could not persist evaluation run to database: {str(e)}")

        return report_response

evaluation_pipeline = EvaluationPipeline()
