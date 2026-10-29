import React from "react";
import { X, ShieldCheck, FileCheck, HelpCircle, Ban, Layers, Clock } from "lucide-react";
import type { EvidenceObject } from "../types";

interface EvidenceDrawerProps {
  evidence: EvidenceObject | null;
  isOpen: boolean;
  onClose: () => void;
  latencyMs?: number;
  retrievalStatus?: string;
  modelStatus?: string;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  evidence,
  isOpen,
  onClose,
  latencyMs,
  retrievalStatus,
}) => {
  if (!isOpen || !evidence) return null;

  const decision = evidence.decision;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end bg-slate-900/40 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg bg-white h-full shadow-2xl border-l border-slate-200 flex flex-col justify-between">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2.5">
            <div className="h-8 w-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">Evidence Verification Inspector</h3>
              <p className="text-xs text-slate-500">Traceable facts verified by Evidence Engine</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Query & Decision Card */}
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Deterministic Decision
              </span>
              <span
                className={`text-xs font-bold px-2.5 py-1 rounded-md flex items-center space-x-1 ${
                  decision === "ANSWER"
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    : decision === "CLARIFY"
                    ? "bg-amber-100 text-amber-800 border border-amber-300"
                    : "bg-rose-100 text-rose-800 border border-rose-300"
                }`}
              >
                {decision === "ANSWER" && <FileCheck className="h-3.5 w-3.5" />}
                {decision === "CLARIFY" && <HelpCircle className="h-3.5 w-3.5" />}
                {decision === "REFUSE" && <Ban className="h-3.5 w-3.5" />}
                <span>{decision}</span>
              </span>
            </div>

            <div>
              <span className="text-xs text-slate-500 block">Evaluated Shopper Query:</span>
              <p className="text-sm font-semibold text-slate-900 mt-0.5">"{evidence.query}"</p>
            </div>

            {/* Performance telemetry */}
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-200 text-xs text-slate-600">
              <div className="flex items-center space-x-1">
                <Clock className="h-3.5 w-3.5 text-slate-400" />
                <span>Latency: {latencyMs ? `${latencyMs.toFixed(1)} ms` : "N/A"}</span>
              </div>
              <div className="flex items-center space-x-1">
                <Layers className="h-3.5 w-3.5 text-slate-400" />
                <span className="truncate">{retrievalStatus || "Hybrid Retrieval"}</span>
              </div>
            </div>
          </div>

          {/* Refusal Reason if applicable */}
          {decision === "REFUSE" && evidence.refusal_reason && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4">
              <div className="flex items-center space-x-2 text-rose-800 font-semibold text-xs mb-1">
                <Ban className="h-4 w-4 text-rose-600" />
                <span>Verified Refusal Grounding</span>
              </div>
              <p className="text-xs text-rose-700 leading-relaxed">
                {evidence.refusal_reason}
              </p>
              <p className="text-[11px] text-rose-600 mt-2 font-medium">
                Invariant: The assistant strictly refused rather than fabricating unverified claims.
              </p>
            </div>
          )}

          {/* Clarification follow-up if applicable */}
          {decision === "CLARIFY" && evidence.clarification_question && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex items-center space-x-2 text-amber-800 font-semibold text-xs mb-1">
                <HelpCircle className="h-4 w-4 text-amber-600" />
                <span>Ambiguity Detected — Clarification Approved</span>
              </div>
              <p className="text-xs text-amber-800 font-medium leading-relaxed">
                {evidence.clarification_question}
              </p>
            </div>
          )}

          {/* Verified Evidence Items */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Verified Ground Truth Items ({evidence.evidence.length})
              </h4>
              <span className="text-[11px] text-emerald-700 font-medium bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                100% Traceable
              </span>
            </div>

            {evidence.evidence.length === 0 ? (
              <p className="text-xs text-slate-500 italic bg-slate-50 p-3 rounded-lg border border-dashed border-slate-200">
                No verified catalogue evidence matched this specific request. Refusal or clarification issued.
              </p>
            ) : (
              <div className="space-y-2.5">
                {evidence.evidence.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-slate-200 bg-white shadow-2xs hover:border-indigo-300 transition-colors"
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                        [{item.source_type.toUpperCase()}:{item.source_id}]
                      </span>
                      <span className="text-[11px] font-semibold text-slate-500 capitalize">
                        field: {item.field}
                      </span>
                    </div>
                    <div className="text-xs text-slate-800 font-medium break-words mt-1 pl-1 border-l-2 border-indigo-400">
                      {String(item.value)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Unsupported Fields (if any) */}
          {evidence.unsupported_fields.length > 0 && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700 block mb-2">
                Requested but Unsupported Information
              </span>
              <div className="flex flex-wrap gap-1.5">
                {evidence.unsupported_fields.map((f, i) => (
                  <span
                    key={i}
                    className="text-xs px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 text-center">
          <p className="text-[11px] text-slate-500">
            TruthCart AI Evidence Engine — Guaranteed Zero Hallucination Pipeline
          </p>
        </div>
      </div>
    </div>
  );
};
