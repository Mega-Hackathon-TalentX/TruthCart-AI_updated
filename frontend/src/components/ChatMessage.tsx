import React from "react";
import { User, ShieldCheck, FileCheck, HelpCircle, Ban, Eye, Scale, Volume2, VolumeX } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../types";
import { ProductCard } from "./ProductCard";

interface ChatMessageProps {
  message: ChatMessageType;
  onOpenEvidence: (msg: ChatMessageType) => void;
  onSelectSuggestion?: (query: string) => void;
  onReportIssue?: (msg: ChatMessageType) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onOpenEvidence,
  onSelectSuggestion,
  onReportIssue,
}) => {
  const isUser = message.sender === "user";
  const decision = message.decision;
  const [isSpeaking, setIsSpeaking] = React.useState(false);

  const handleToggleSpeak = () => {
    if (!("speechSynthesis" in window)) return;

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    const cleanText = message.text
      .replace(/\[(PRODUCT|POLICY):[^\]]+\]/g, "")
      .replace(/[•\*\#]/g, "")
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="flex items-start max-w-xl space-x-2.5">
          <div className="bg-blue-600 text-white rounded-2xl rounded-tr-xs px-4 py-3 shadow-xs">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
            <span className="text-[10px] text-blue-200 block text-right mt-1">
              {message.timestamp}
            </span>
          </div>
          <div className="h-8 w-8 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center shrink-0">
            <User className="h-4 w-4" />
          </div>
        </div>
      </div>
    );
  }

  // Assistant Message
  return (
    <div className="flex justify-start mb-6 animate-fade-in">
      <div className="flex items-start max-w-3xl w-full space-x-3">
        {/* Assistant Avatar */}
        <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-700 to-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs ring-2 ring-indigo-50">
          <ShieldCheck className="h-5 w-5" />
        </div>

        {/* Message Content Container */}
        <div className="flex-1 bg-white rounded-2xl rounded-tl-xs border border-slate-200/90 p-5 shadow-xs space-y-4">
          {/* Header Info: Decision badge & Inspector button */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center space-x-2">
              {decision && (
                <span
                  className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full flex items-center space-x-1 ${
                    decision === "ANSWER"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : decision === "CLARIFY"
                      ? "bg-amber-50 text-amber-800 border border-amber-200"
                      : "bg-rose-50 text-rose-700 border border-rose-200"
                  }`}
                >
                  {decision === "ANSWER" && <FileCheck className="h-3 w-3" />}
                  {decision === "CLARIFY" && <HelpCircle className="h-3 w-3" />}
                  {decision === "REFUSE" && <Ban className="h-3 w-3" />}
                  <span>{decision}</span>
                </span>
              )}

              {message.citations && message.citations.length > 0 && (
                <span className="text-[11px] text-indigo-700 font-semibold bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
                  {message.citations.length} Verified Citation{message.citations.length > 1 ? "s" : ""}
                </span>
              )}
            </div>

            <div className="flex items-center space-x-2">
              {"speechSynthesis" in window && (
                <button
                  type="button"
                  onClick={handleToggleSpeak}
                  className={`p-1.5 rounded-lg border transition-colors flex items-center cursor-pointer ${
                    isSpeaking
                      ? "bg-indigo-600 text-white border-indigo-600 animate-pulse"
                      : "text-slate-500 hover:text-indigo-600 bg-slate-50 hover:bg-indigo-50 border-slate-200"
                  }`}
                  title={isSpeaking ? "Stop speaking" : "Listen to response"}
                >
                  {isSpeaking ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                </button>
              )}

              {/* View Evidence / Traceability Button */}
              {message.evidence && (
                <button
                  onClick={() => onOpenEvidence(message)}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50/80 hover:bg-indigo-100 px-3 py-1 rounded-lg border border-indigo-200 transition-colors flex items-center space-x-1.5 cursor-pointer"
                  title="View verified evidence and decision engine trace"
                >
                  <Eye className="h-3.5 w-3.5" />
                  <span>View Evidence</span>
                </button>
              )}
            </div>
          </div>

          {/* Response Text */}
          <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {message.text}
          </div>

          {/* Clarification prompt suggestions if applicable */}
          {decision === "CLARIFY" && onSelectSuggestion && (
            <div className="pt-2 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-500 block mb-2">
                Quick Clarification Options:
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => onSelectSuggestion("Under ₹2,000")}
                  className="text-xs font-medium px-3 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer"
                >
                  Under ₹2,000
                </button>
                <button
                  onClick={() => onSelectSuggestion("Pure cotton material")}
                  className="text-xs font-medium px-3 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer"
                >
                  Cotton material
                </button>
                <button
                  onClick={() => onSelectSuggestion("In stock only")}
                  className="text-xs font-medium px-3 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer"
                >
                  In stock items
                </button>
              </div>
            </div>
          )}

          {/* Comparison Matrix Table if comparison data is present */}
          {message.comparison_data && message.comparison_data.products.length >= 2 && (
            <div className="pt-2">
              <div className="flex items-center space-x-2 mb-3">
                <Scale className="h-4 w-4 text-indigo-600" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Side-by-Side Product Comparison ({message.comparison_data.products.length} Products)
                </span>
              </div>
              <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/50 shadow-xs">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-100/80 border-b border-slate-200">
                        <th className="px-3.5 py-2.5 font-bold text-slate-500 uppercase text-[10px] w-32">Specification</th>
                        {message.comparison_data.products.map((pid) => (
                          <th key={pid} className="px-3.5 py-2.5 font-bold text-slate-900 min-w-44">
                            <div className="flex flex-col space-y-1">
                              <span className="truncate">{message.comparison_data!.product_titles[pid] || pid}</span>
                              <span className="font-mono text-[10px] text-indigo-600 font-semibold">[PRODUCT:{pid}]</span>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200/60 bg-white">
                      {Object.entries(message.comparison_data.dimensions).map(([dimName, dimVals]) => (
                        <tr key={dimName}>
                          <td className="px-3.5 py-2 font-semibold text-slate-600 bg-slate-50/60">
                            {dimName}
                          </td>
                          {message.comparison_data!.products.map((pid) => {
                            const val = dimVals[pid];
                            return (
                              <td key={pid} className="px-3.5 py-2 text-slate-800">
                                {val !== undefined ? (
                                  Array.isArray(val) ? val.join(", ") : String(val)
                                ) : (
                                  <span className="text-slate-400 italic">Not documented</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Product Cards Grid if supported products present (only if not a multi-product comparison table) */}
          {(!message.comparison_data || message.comparison_data.products.length < 2) && message.products && message.products.length > 0 && (
            <div className="pt-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-3">
                Verified Catalogue Records ({message.products.length})
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {message.products.map((prod) => (
                  <ProductCard
                    key={prod.product_id}
                    product={prod}
                    onViewEvidence={() => onOpenEvidence(message)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Telemetry Footer */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>
              {message.retrieval_status || "Ground Truth Retrieval"} • {message.model_status}
            </span>
            <div className="flex items-center space-x-3">
              {onReportIssue && (
                <button
                  onClick={() => onReportIssue(message)}
                  className="text-slate-400 hover:text-indigo-600 transition-colors font-medium cursor-pointer"
                  title="Submit feedback or report an incorrect claim to store owner"
                >
                  Report Issue
                </button>
              )}
              <span>
                {message.latency_ms ? `${message.latency_ms.toFixed(0)}ms latency` : ""}
                {message.token_cost !== undefined ? ` • $${message.token_cost.toFixed(4)} token cost` : ""}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

