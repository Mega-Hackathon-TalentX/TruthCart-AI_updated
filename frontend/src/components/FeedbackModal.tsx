import React, { useState } from "react";
import { X, MessageSquarePlus, Star, CheckCircle2, AlertCircle } from "lucide-react";
import { submitFeedback } from "../services/api";
import type { FeedbackItem } from "../types";

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  prefillProductId?: string;
  prefillConversationId?: string;
  onSuccess?: (item: FeedbackItem) => void;
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  onClose,
  prefillProductId,
  prefillConversationId,
  onSuccess,
}) => {
  const [feedbackType, setFeedbackType] = useState<string>("incorrect_product_info");
  const [productId, setProductId] = useState<string>(prefillProductId || "");
  const [message, setMessage] = useState<string>("");
  const [rating, setRating] = useState<number>(5);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successItem, setSuccessItem] = useState<FeedbackItem | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) {
      setError("Please describe the issue or feedback.");
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const fb = await submitFeedback({
        feedback_type: feedbackType,
        message: message.trim(),
        product_id: productId.trim() || undefined,
        conversation_id: prefillConversationId,
        rating,
      });
      setSuccessItem(fb);
      if (onSuccess) onSuccess(fb);
    } catch (err: any) {
      setError(err.message || "Failed to submit feedback. Please ensure you are logged in.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSuccessItem(null);
    setMessage("");
    setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-700 via-indigo-600 to-violet-700 p-5 text-white flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-white/10 backdrop-blur-xs">
              <MessageSquarePlus className="h-5 w-5 text-indigo-200" />
            </div>
            <div>
              <h3 className="text-base font-bold tracking-tight">Report Issue / Submit Feedback</h3>
              <p className="text-xs text-indigo-100">
                TruthCart AI audits every report. Official records are only modified by store owner approval.
              </p>
            </div>
          </div>
          <button
            onClick={handleReset}
            className="p-1 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {successItem ? (
            <div className="text-center py-6 space-y-4">
              <div className="h-14 w-14 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8" />
              </div>
              <h4 className="text-lg font-bold text-slate-900">Feedback Saved to Database</h4>
              <p className="text-xs text-slate-600 max-w-sm mx-auto leading-relaxed">
                Thank you! Your report has been persisted with ID:{" "}
                <code className="bg-slate-100 px-1 py-0.5 rounded text-[11px] font-mono text-indigo-600">
                  {successItem.id.slice(0, 8)}...
                </code>
                . It is marked as <strong className="text-amber-600">PENDING</strong>. A store owner will review official vendor proof before applying verified changes.
              </p>
              <div className="pt-2">
                <button
                  onClick={handleReset}
                  className="px-5 py-2 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-700 transition-colors cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start space-x-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-500" />
                  <span>{error}</span>
                </div>
              )}

              {/* Feedback Category */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Report Category
                </label>
                <select
                  value={feedbackType}
                  onChange={(e) => setFeedbackType(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900"
                >
                  <option value="incorrect_product_info">Incorrect Price or Specification</option>
                  <option value="ai_answer">Inaccurate AI Assistant Answer</option>
                  <option value="incorrect_attribute">Incorrect or Missing Attribute</option>
                  <option value="missing_product">Missing Product from Catalogue</option>
                  <option value="recommendation_issue">Recommendation Disregarded My Budget</option>
                  <option value="catalogue_issue">General Catalogue Issue</option>
                  <option value="general_usability">Usability Feedback / Suggestion</option>
                </select>
              </div>

              {/* Relevant Product ID */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Product ID (Optional SKU)
                </label>
                <input
                  type="text"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  placeholder="e.g. TC-EL-201"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900"
                />
              </div>

              {/* Message */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Description of Issue or Feedback
                </label>
                <textarea
                  required
                  rows={3}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Explain what is incorrect or what you expected to see..."
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900 resize-none"
                />
              </div>

              {/* Star Rating */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Rating of Answer Experience
                </label>
                <div className="flex items-center space-x-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRating(star)}
                      className="p-1 text-slate-300 hover:text-amber-400 focus:outline-hidden transition-colors cursor-pointer"
                    >
                      <Star
                        className={`h-5 w-5 ${
                          star <= rating
                            ? "text-amber-400 fill-amber-400"
                            : "text-slate-300"
                        }`}
                      />
                    </button>
                  ))}
                  <span className="text-xs font-medium text-slate-500 ml-2">
                    {rating} / 5 Stars
                  </span>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
                >
                  {isLoading ? "Submitting..." : "Submit to Store Owner"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
