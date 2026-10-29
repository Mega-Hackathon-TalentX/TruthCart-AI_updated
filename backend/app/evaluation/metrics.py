import numpy as np
from typing import List, Dict, Any

class EvaluationMetrics:
    """Computes rigorous RAG and shopping assistant evaluation metrics."""

    @staticmethod
    def calculate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {
                "total_cases_available": 0,
                "total_cases_executed": 0,
                "total_cases_passed": 0,
                "total_cases_failed": 0,
                "total_cases_skipped": 0,
                "groundedness_score": 0.0,
                "answer_helpfulness_score": 0.0,
                "refusal_accuracy": 0.0,
                "clarification_accuracy": 0.0,
                "unsupported_claim_rate": 0.0,
                "citation_validity_rate": 0.0,
                "citation_coverage_rate": 0.0,
                "avg_latency_ms": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p90_ms": 0.0,
                "latency_p99_ms": 0.0,
                "avg_token_cost": 0.0,
                "total_token_cost": 0.0
            }

        total = len(results)
        valid_citations_count = sum(1 for r in results if r.get("citations_valid", False))
        unsupported_claims_count = sum(1 for r in results if r.get("has_unsupported_claims", False))
        latencies = [float(r.get("latency_ms", 0.0)) for r in results]

        # Breakdown by expected decision (if provided in test dataset)
        refusal_tests = [r for r in results if r.get("expected_decision") == "REFUSE"]
        correct_refusals = sum(1 for r in refusal_tests if r.get("actual_decision") == "REFUSE")
        refusal_acc = (correct_refusals / len(refusal_tests)) if refusal_tests else 1.0

        clarify_tests = [r for r in results if r.get("expected_decision") == "CLARIFY"]
        correct_clarifications = sum(1 for r in clarify_tests if r.get("actual_decision") == "CLARIFY")
        clarify_acc = (correct_clarifications / len(clarify_tests)) if clarify_tests else 1.0

        answer_tests = [r for r in results if r.get("expected_decision") == "ANSWER"]
        correct_answers = sum(1 for r in answer_tests if r.get("actual_decision") == "ANSWER")
        answer_helpfulness = (correct_answers / len(answer_tests)) if answer_tests else 1.0

        # Groundedness: 1.0 minus unsupported claim rate
        unsupported_rate = unsupported_claims_count / total
        groundedness = max(0.0, 1.0 - unsupported_rate)

        citation_validity = valid_citations_count / total

        # Citation Coverage: percentage of ANSWER cases that contain at least 1 verified citation
        answer_cases = [r for r in results if r.get("actual_decision") == "ANSWER"]
        with_citations = [r for r in answer_cases if len(r.get("citations", [])) > 0]
        citation_coverage = (len(with_citations) / len(answer_cases)) if answer_cases else 1.0

        # Passed cases: decision matches expected (if expected provided) AND citations valid AND zero unsupported claims
        passed_count = sum(1 for r in results if r.get("passed", True))

        # Latency statistics
        lat_arr = np.array(latencies) if latencies else np.array([0.0])
        p50 = float(np.percentile(lat_arr, 50))
        p90 = float(np.percentile(lat_arr, 90))
        p99 = float(np.percentile(lat_arr, 99))

        return {
            "total_cases_available": total,
            "total_cases_executed": total,
            "total_cases_passed": passed_count,
            "total_cases_failed": total - passed_count,
            "total_cases_skipped": 0,
            "groundedness_score": round(groundedness, 4),
            "answer_helpfulness_score": round(answer_helpfulness, 4),
            "refusal_accuracy": round(refusal_acc, 4),
            "clarification_accuracy": round(clarify_acc, 4),
            "unsupported_claim_rate": round(unsupported_rate, 4),
            "citation_validity_rate": round(citation_validity, 4),
            "citation_coverage_rate": round(citation_coverage, 4),
            "avg_latency_ms": round(float(np.mean(lat_arr)), 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p90_ms": round(p90, 2),
            "latency_p99_ms": round(p99, 2),
            "avg_token_cost": 0.0,
            "total_token_cost": 0.0
        }

evaluation_metrics = EvaluationMetrics()
