import React, { useState, useEffect } from "react";
import { MessageSquare } from "lucide-react";
import {
  fetchOwnerFeedback,
  updateFeedbackStatus,
  applyVerifiedCorrection,
  fetchProduct
} from "../services/api";
import type { FeedbackItem, ProductItem } from "../types";

export const OwnerFeedbackView: React.FC = () => {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [statusNote, setStatusNote] = useState<string>("");

  // Correction Modal State
  const [correctionTarget, setCorrectionTarget] = useState<FeedbackItem | null>(null);
  const [newPrice, setNewPrice] = useState<string>("");
  const [newStock, setNewStock] = useState<string>("");
  const [resolutionNote, setResolutionNote] = useState<string>("");
  const [isApplyingCorrection, setIsApplyingCorrection] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    loadFeedback();
  }, [statusFilter]);

  const loadFeedback = async () => {
    setIsLoading(true);
    try {
      const data = await fetchOwnerFeedback({
        status: statusFilter || undefined,
      });
      setFeedbacks(data);
    } catch (err: any) {
      setActionError(err.message || "Failed to load feedback");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateStatus = async (fbId: string, newStatus: string) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await updateFeedbackStatus(fbId, newStatus, statusNote || `Status changed to ${newStatus} by owner.`);
      setActionSuccess(`Feedback marked as ${newStatus}.`);
      setStatusNote("");
      await loadFeedback();
    } catch (err: any) {
      setActionError(err.message || "Failed to update feedback status.");
    }
  };

  const handleOpenCorrection = async (fb: FeedbackItem) => {
    setCorrectionTarget(fb);
    setActionError(null);
    setActionSuccess(null);
    setResolutionNote(`Verified correction on customer report: ${fb.id.slice(0, 8)}`);

    if (fb.product_id) {
      try {
        const prod = await fetchProduct(fb.product_id);
        setNewPrice(String(prod.price));
        setNewStock(prod.stock_status);
      } catch {
        // Fallback
      }
    }
  };

  const handleExecuteCorrection = async () => {
    if (!correctionTarget || !correctionTarget.product_id) return;
    setIsApplyingCorrection(true);
    setActionError(null);

    try {
      const updates: Partial<ProductItem> = {};
      if (newPrice) updates.price = parseFloat(newPrice);
      if (newStock) updates.stock_status = newStock;

      await applyVerifiedCorrection({
        feedback_id: correctionTarget.id,
        product_id: correctionTarget.product_id,
        updates,
        resolution_note: resolutionNote || "Official product verified against vendor ground truth.",
      });

      setActionSuccess(`Verified correction applied on ${correctionTarget.product_id}. Feedback marked RESOLVED.`);
      setCorrectionTarget(null);
      await loadFeedback();
    } catch (err: any) {
      setActionError(err.message || "Failed to apply verified correction.");
    } finally {
      setIsApplyingCorrection(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <MessageSquare className="h-6 w-6 text-indigo-600" />
            <span>Customer Feedback & Ground Truth Review</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            <strong>Critical Policy:</strong> Customer comments never alter official data automatically. You must verify facts against trusted sources before updating products.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
          {["", "PENDING", "UNDER_REVIEW", "RESOLVED", "REJECTED"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl transition-colors cursor-pointer ${
                statusFilter === st
                  ? "bg-indigo-600 text-white shadow-2xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {st === "" ? "All Reports" : st.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between">
          <span>{actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-500 hover:text-emerald-700">✕</button>
        </div>
      )}

      {actionError && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* Feedback Items Grid */}
      {isLoading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Loading customer feedback submissions...</div>
      ) : feedbacks.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-400 text-xs">
          No feedback reports matching filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {feedbacks.map((fb) => (
            <div
              key={fb.id}
              className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                      {fb.feedback_type.replace(/_/g, " ")}
                    </span>
                    {fb.is_demo && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                        Demo Fixture
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      fb.status === "PENDING"
                        ? "bg-amber-100 text-amber-800"
                        : fb.status === "UNDER_REVIEW"
                        ? "bg-blue-100 text-blue-800"
                        : fb.status === "RESOLVED"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-rose-100 text-rose-800"
                    }`}
                  >
                    {fb.status}
                  </span>
                </div>

                <div className="text-xs text-slate-500 flex items-center justify-between">
                  <span>Customer: <strong className="text-slate-700">{fb.customer_email}</strong></span>
                  {fb.product_id && (
                    <span className="font-mono font-semibold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded">
                      SKU: {fb.product_id}
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-800 font-medium p-3 rounded-xl bg-slate-50 border border-slate-100 leading-relaxed">
                  "{fb.message}"
                </p>

                {fb.owner_resolution_note && (
                  <div className="text-[11px] text-emerald-800 bg-emerald-50/70 p-2.5 rounded-xl border border-emerald-200 space-y-0.5">
                    <strong>Owner Resolution Note:</strong>
                    <p>{fb.owner_resolution_note}</p>
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="text-[10px] text-slate-400">
                  {new Date(fb.created_at).toLocaleString()}
                </span>

                <div className="flex items-center space-x-1.5">
                  {fb.status !== "UNDER_REVIEW" && fb.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleUpdateStatus(fb.id, "UNDER_REVIEW")}
                      className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 font-semibold text-[11px] cursor-pointer"
                    >
                      Under Review
                    </button>
                  )}

                  {fb.product_id && fb.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleOpenCorrection(fb)}
                      className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 font-semibold text-[11px] shadow-2xs cursor-pointer"
                    >
                      Verify & Correct SKU
                    </button>
                  )}

                  {fb.status !== "REJECTED" && fb.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleUpdateStatus(fb.id, "REJECTED")}
                      className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 hover:bg-rose-50 hover:text-rose-700 font-semibold text-[11px] cursor-pointer"
                    >
                      Reject
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Verified Correction Modal */}
      {correctionTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden space-y-4 p-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Verified Correction: {correctionTarget.product_id}
                </h3>
                <span className="text-xs text-slate-400">
                  Update official values based on verified manufacturer proof.
                </span>
              </div>
              <button onClick={() => setCorrectionTarget(null)} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer">
                ✕
              </button>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
              <strong>Customer Report:</strong> "{correctionTarget.message}"
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Verified Price (₹)
                </label>
                <input
                  type="number"
                  value={newPrice}
                  onChange={(e) => setNewPrice(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Verified Stock Status
                </label>
                <select
                  value={newStock}
                  onChange={(e) => setNewStock(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                >
                  <option value="In Stock">In Stock</option>
                  <option value="Out of Stock">Out of Stock</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Owner Resolution & Ground Truth Audit Note
                </label>
                <textarea
                  rows={3}
                  value={resolutionNote}
                  onChange={(e) => setResolutionNote(e.target.value)}
                  placeholder="State evidence checked e.g. 'Verified with vendor tax invoice #1024.'..."
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white resize-none"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
              <button
                onClick={() => setCorrectionTarget(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteCorrection}
                disabled={isApplyingCorrection}
                className="px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm cursor-pointer disabled:opacity-50"
              >
                {isApplyingCorrection ? "Updating & Re-indexing..." : "Apply Verified Change & Resolve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
