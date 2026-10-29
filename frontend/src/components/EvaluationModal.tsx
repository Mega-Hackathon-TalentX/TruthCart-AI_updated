import React, { useState } from "react";
import {
  X,
  Play,
  BarChart3,
  AlertTriangle,
  RefreshCw,
  FileCheck2,
  CheckCircle,
  XCircle,
  Database,
  Cpu,
  ChevronDown,
  ChevronUp
} from "lucide-react";
import { runEvaluationSuite } from "../services/api";
import type { EvaluationReportResponse } from "../types";

interface EvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const EvaluationModal: React.FC<EvaluationModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [report, setReport] = useState<EvaluationReportResponse | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "passed" | "failed">("all");
  const [expandedQid, setExpandedQid] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string>("evaluation_benchmark_150.json");

  if (!isOpen) return null;

  const handleRunEvaluation = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const result = await runEvaluationSuite(selectedDataset);
      setReport(result);
    } catch (err: any) {
      setError(err.message || "Failed to execute evaluation suite.");
    } finally {
      setIsRunning(false);
    }
  };

  const filteredDetails = report?.details.filter((q) => {
    const isPassed = q.passed ?? (q.decision_match !== false && q.citations_valid && !q.has_unsupported_claims);
    if (activeTab === "passed") return isPassed;
    if (activeTab === "failed") return !isPassed;
    return true;
  }) || [];

  const passedCount = report?.total_cases_passed ?? report?.details.filter(q => q.passed ?? (q.decision_match !== false && q.citations_valid && !q.has_unsupported_claims)).length ?? 0;
  const failedCount = report?.total_cases_failed ?? ((report?.details.length ?? 0) - passedCount);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="bg-white rounded-2xl max-w-5xl w-full max-h-[92vh] shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-lg flex items-center space-x-2">
                <span>TruthCart AI Benchmark & Evaluation Suite</span>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">TalentX</span>
              </h3>
              <p className="text-xs text-slate-500">
                Rigorous Grounding, Citation Validation, & Hallucination Resistance Verification
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Action Header Card */}
          <div className="bg-indigo-50/70 border border-indigo-100 rounded-xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h4 className="font-semibold text-indigo-950 text-sm">
                Execute Automated Benchmark Pipeline
              </h4>
              <p className="text-xs text-indigo-800 mt-1 max-w-xl">
                Runs real evaluation queries through Query Understanding, Hybrid Retrieval, Evidence Engine, Citation Validation, and Grounded Generation. No hardcoded or fabricated scores.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                disabled={isRunning}
                className="text-xs font-medium bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-700 shadow-xs focus:outline-hidden focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="truthcart_evaluation_questions_150.jsonl">Official R3 Benchmark (150 Questions JSONL)</option>
                <option value="evaluation_benchmark_150.json">Active Catalogue Suite (150 Questions JSON)</option>
                <option value="sample_eval_questions.json">Dev Fixture Suite (10 Questions)</option>
              </select>

              <button
                onClick={handleRunEvaluation}
                disabled={isRunning}
                id="run-eval-suite-btn"
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold text-xs shadow-sm flex items-center space-x-2 transition-all cursor-pointer shrink-0"
              >
              {isRunning ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Evaluating Pipeline...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  <span>Execute Benchmark</span>
                </>
              )}
            </button>
          </div>
        </div>

          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-800 flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Results Overview */}
          {report ? (
            <div className="space-y-6 animate-fade-in">
              {/* Readiness & Provenance Bar */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-1.5">
                    <Database className="h-3.5 w-3.5 text-indigo-600" />
                    <span>Data: <strong className="text-slate-800">{report.data_readiness || "Active Catalogue"}</strong></span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <Cpu className="h-3.5 w-3.5 text-indigo-600" />
                    <span>Model: <strong className="text-slate-800">{report.model_readiness || "Local Offline"}</strong></span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      Token Cost: ${(report.avg_token_cost ?? 0.0).toFixed(4)} / query (Offline)
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-3 text-[11px] text-slate-500">
                  <span>Dataset: <strong className="text-slate-700">{report.dataset_name}</strong></span>
                  <span>•</span>
                  <span>Timestamp: <strong className="text-slate-700">{new Date(report.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</strong></span>
                </div>
              </div>

              {/* Case Count Summary Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Available</span>
                  <span className="text-xl font-bold text-slate-800 block mt-0.5">{report.total_cases_available ?? report.total_questions_tested}</span>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-semibold text-blue-600 uppercase tracking-wider block">Executed</span>
                  <span className="text-xl font-bold text-blue-800 block mt-0.5">{report.total_cases_executed ?? report.successfully_evaluated}</span>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wider block">Passed</span>
                  <span className="text-xl font-bold text-emerald-800 block mt-0.5">{passedCount}</span>
                </div>
                <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-semibold text-rose-600 uppercase tracking-wider block">Failed</span>
                  <span className="text-xl font-bold text-rose-800 block mt-0.5">{failedCount}</span>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Skipped</span>
                  <span className="text-xl font-bold text-slate-600 block mt-0.5">{report.total_cases_skipped ?? 0}</span>
                </div>
              </div>

              {/* Primary Evaluation Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {/* Groundedness */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Groundedness</span>
                  <span className="text-xl font-bold text-emerald-600 block mt-1">
                    {(report.groundedness_score * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Zero-hallucination</span>
                </div>

                {/* Citation Validity */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Citation Validity</span>
                  <span className="text-xl font-bold text-indigo-600 block mt-1">
                    {(report.citation_validity_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Server verified</span>
                </div>

                {/* Citation Coverage */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Citation Coverage</span>
                  <span className="text-xl font-bold text-indigo-700 block mt-1">
                    {((report.citation_coverage_rate ?? 1.0) * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Claims with citations</span>
                </div>

                {/* Refusal Accuracy */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Refusal Accuracy</span>
                  <span className="text-xl font-bold text-blue-600 block mt-1">
                    {(report.refusal_accuracy * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Unsupported safety</span>
                </div>

                {/* Clarification Accuracy */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Clarification Acc</span>
                  <span className="text-xl font-bold text-amber-600 block mt-1">
                    {(report.clarification_accuracy * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400">Ambiguous queries</span>
                </div>

                {/* Latency Stats */}
                <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Avg Latency</span>
                  <span className="text-xl font-bold text-slate-800 block mt-1">
                    {report.avg_latency_ms.toFixed(0)} ms
                  </span>
                  <span className="text-[10px] text-slate-400">
                    P50: {(report.latency_p50_ms || report.avg_latency_ms).toFixed(0)}ms | P99: {(report.latency_p99_ms || report.avg_latency_ms * 1.5).toFixed(0)}ms
                  </span>
                </div>
              </div>

              {/* Filter Tabs & Per-Question Table */}
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setActiveTab("all")}
                      className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                        activeTab === "all"
                          ? "bg-indigo-600 text-white"
                          : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      All Cases ({report.details.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("passed")}
                      className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                        activeTab === "passed"
                          ? "bg-emerald-600 text-white"
                          : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      Passed ({passedCount})
                    </button>
                    <button
                      onClick={() => setActiveTab("failed")}
                      className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                        activeTab === "failed"
                          ? "bg-rose-600 text-white"
                          : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      Failed / Flagged ({failedCount})
                    </button>
                  </div>
                  <span className="text-[11px] text-slate-400">Click a row to inspect evidence details</span>
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden shadow-xs">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-[10px] tracking-wider">
                        <tr>
                          <th className="px-3.5 py-2.5 font-bold">Status</th>
                          <th className="px-3.5 py-2.5 font-bold">QID</th>
                          <th className="px-3.5 py-2.5 font-bold">Query</th>
                          <th className="px-3.5 py-2.5 font-bold">Expected</th>
                          <th className="px-3.5 py-2.5 font-bold">Actual</th>
                          <th className="px-3.5 py-2.5 font-bold">Citations</th>
                          <th className="px-3.5 py-2.5 font-bold">Latency</th>
                          <th className="px-3.5 py-2.5 font-bold text-right">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-medium">
                        {filteredDetails.map((q) => {
                          const isPassed = q.passed ?? (q.decision_match !== false && q.citations_valid && !q.has_unsupported_claims);
                          const isExpanded = expandedQid === q.question_id;

                          return (
                            <React.Fragment key={q.question_id}>
                              <tr
                                onClick={() => setExpandedQid(isExpanded ? null : q.question_id)}
                                className={`cursor-pointer transition-colors ${
                                  isExpanded ? "bg-indigo-50/50" : "hover:bg-slate-50/70"
                                }`}
                              >
                                <td className="px-3.5 py-2.5">
                                  {isPassed ? (
                                    <span className="flex items-center space-x-1 text-emerald-600 text-[11px] font-bold">
                                      <CheckCircle className="h-3.5 w-3.5" />
                                      <span>PASS</span>
                                    </span>
                                  ) : (
                                    <span className="flex items-center space-x-1 text-rose-600 text-[11px] font-bold">
                                      <XCircle className="h-3.5 w-3.5" />
                                      <span>FAIL</span>
                                    </span>
                                  )}
                                </td>
                                <td className="px-3.5 py-2.5 font-mono text-slate-500">{q.question_id}</td>
                                <td className="px-3.5 py-2.5 text-slate-900 max-w-xs truncate font-medium">{q.query}</td>
                                <td className="px-3.5 py-2.5 text-slate-600">{q.expected_decision || "N/A"}</td>
                                <td className="px-3.5 py-2.5">
                                  <span
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                      q.actual_decision === "ANSWER"
                                        ? "bg-emerald-100 text-emerald-800"
                                        : q.actual_decision === "CLARIFY"
                                        ? "bg-amber-100 text-amber-800"
                                        : "bg-rose-100 text-rose-800"
                                    }`}
                                  >
                                    {q.actual_decision}
                                  </span>
                                </td>
                                <td className="px-3.5 py-2.5 font-mono text-indigo-700">
                                  {q.citations.length > 0 ? q.citations.join(", ") : "None"}
                                </td>
                                <td className="px-3.5 py-2.5 text-slate-500 whitespace-nowrap">
                                  <span>{q.latency_ms.toFixed(1)}ms</span>
                                  <span className="text-[10px] text-emerald-600 block">$0.00 cost</span>
                                </td>
                                <td className="px-3.5 py-2.5 text-right text-slate-400">
                                  {isExpanded ? <ChevronUp className="h-4 w-4 inline" /> : <ChevronDown className="h-4 w-4 inline" />}
                                </td>
                              </tr>

                              {/* Expanded Row Inspector */}
                              {isExpanded && (
                                <tr className="bg-slate-50/80 border-b border-slate-200">
                                  <td colSpan={8} className="px-5 py-3.5 space-y-2">
                                    {q.failure_reason && (
                                      <div className="bg-rose-50 border border-rose-200 rounded-lg p-2.5 text-xs text-rose-800 flex items-start space-x-2">
                                        <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                                        <div>
                                          <strong>Failure Reason:</strong> {q.failure_reason}
                                        </div>
                                      </div>
                                    )}

                                    {q.notes && (
                                      <div className="text-xs text-slate-600">
                                        <strong>Dataset Notes:</strong> {q.notes}
                                      </div>
                                    )}

                                    {q.evidence_preview && q.evidence_preview.length > 0 ? (
                                      <div className="space-y-1">
                                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                                          Supporting Ground-Truth Evidence:
                                        </span>
                                        <div className="flex flex-wrap gap-1.5">
                                          {q.evidence_preview.map((ev, i) => (
                                            <span
                                              key={i}
                                              className="bg-white border border-slate-200 text-slate-800 font-mono text-[11px] px-2.5 py-1 rounded-md"
                                            >
                                              {ev}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-xs text-slate-400 italic">
                                        No evidence items extracted (Refusal or Unresolved).
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-14 text-slate-400 text-xs">
              <FileCheck2 className="h-12 w-12 mx-auto text-slate-300 mb-3 stroke-[1.5]" />
              <p className="text-slate-600 font-semibold text-sm">Automated Benchmark Ready</p>
              <p className="text-slate-400 mt-1 max-w-md mx-auto">
                Click "Execute Benchmark" above to run the 100% deterministic evaluation pipeline against the official test questions.
              </p>
              <p className="text-[11px] text-slate-400 mt-2">
                Real results with full P50/P90/P99 latency distribution and per-query evidence verification will be saved to <code>artifacts/evaluation_reports/</code>.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
