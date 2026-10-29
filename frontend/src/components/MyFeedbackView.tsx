import React, { useState, useEffect } from "react";
import { MessageSquare, Clock, CheckCircle2, XCircle, AlertCircle, Plus } from "lucide-react";
import { fetchMyFeedback } from "../services/api";
import type { FeedbackItem, User } from "../types";

interface MyFeedbackViewProps {
  currentUser: User | null;
  onOpenNewFeedback: () => void;
  onOpenLogin: () => void;
}

export const MyFeedbackView: React.FC<MyFeedbackViewProps> = ({
  currentUser,
  onOpenNewFeedback,
  onOpenLogin,
}) => {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    if (currentUser) {
      loadFeedbacks();
    } else {
      setIsLoading(false);
    }
  }, [currentUser]);

  const loadFeedbacks = async () => {
    setIsLoading(true);
    try {
      const data = await fetchMyFeedback();
      setFeedbacks(data);
    } catch (err) {
      console.error("Failed to load feedback:", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentUser) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center space-y-4">
        <div className="h-14 w-14 rounded-2xl bg-indigo-50 text-indigo-600 mx-auto flex items-center justify-center">
          <MessageSquare className="h-7 w-7" />
        </div>
        <h3 className="text-xl font-bold text-slate-900">Sign In to View Your Feedback</h3>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Customer feedback is privately isolated per user. Log in to track your reported issues and view verified store owner resolutions.
        </p>
        <button
          onClick={onOpenLogin}
          className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer"
        >
          Sign In / Register
        </button>
      </div>
    );
  }

  const getStatusBadge = (status: FeedbackItem["status"]) => {
    switch (status) {
      case "PENDING":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="h-3 w-3" />
            <span>Pending Review</span>
          </span>
        );
      case "UNDER_REVIEW":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <AlertCircle className="h-3 w-3" />
            <span>Under Owner Review</span>
          </span>
        );
      case "RESOLVED":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="h-3 w-3" />
            <span>Verified & Resolved</span>
          </span>
        );
      case "REJECTED":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="h-3 w-3" />
            <span>Rejected</span>
          </span>
        );
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      {/* Top Banner */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <MessageSquare className="h-5 w-5 text-indigo-600" />
            <span>My Submitted Feedback</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Logged in as <strong>{currentUser.email}</strong>. Only you can view your personal feedback history.
          </p>
        </div>

        <button
          onClick={onOpenNewFeedback}
          className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-indigo-600 text-white font-semibold text-xs hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer shrink-0"
        >
          <Plus className="h-4 w-4" />
          <span>Report New Issue</span>
        </button>
      </div>

      {/* Feedbacks list */}
      {isLoading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Loading your feedback history...</div>
      ) : feedbacks.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 space-y-3">
          <div className="h-12 w-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
            <MessageSquare className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-slate-800">No Feedback Submitted Yet</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Notice a wrong price, missing product, or incorrect specification while shopping? Submit feedback and help improve our catalogue.
          </p>
          <button
            onClick={onOpenNewFeedback}
            className="mt-2 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
          >
            Submit First Report
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {feedbacks.map((fb) => (
            <div
              key={fb.id}
              className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs space-y-3 hover:border-slate-300 transition-colors"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-slate-900 capitalize">
                    {fb.feedback_type.replace(/_/g, " ")}
                  </span>
                  {fb.is_demo && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                      Demo Fixture
                    </span>
                  )}
                  {fb.product_id && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold border border-slate-200">
                      SKU: {fb.product_id}
                    </span>
                  )}
                </div>
                {getStatusBadge(fb.status)}
              </div>

              <p className="text-xs text-slate-700 leading-relaxed font-medium">
                "{fb.message}"
              </p>

              {/* Owner Resolution Note if present */}
              {fb.owner_resolution_note && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 block">
                    Store Owner Verified Resolution Note:
                  </span>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {fb.owner_resolution_note}
                  </p>
                  {fb.resolved_at && (
                    <span className="text-[10px] text-slate-400 block pt-1">
                      Resolved on: {new Date(fb.resolved_at).toLocaleString()}
                    </span>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                <span>Submitted: {new Date(fb.created_at).toLocaleString()}</span>
                {fb.rating && (
                  <span className="font-semibold text-amber-600">
                    Rating: {fb.rating} / 5
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
