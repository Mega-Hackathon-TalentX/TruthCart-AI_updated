import { isDemoSession } from "../services/demoService";
import React, { useState, useEffect } from "react";
import { FileText, Save, ShieldCheck } from "lucide-react";
import { fetchActivePolicy, updatePolicy } from "../services/api";
import type { PolicyData } from "../types";

interface OwnerPolicyViewProps {
  isDemo?: boolean;
}

export const OwnerPolicyView: React.FC<OwnerPolicyViewProps> = ({ isDemo: propIsDemo }) => {
  const isDemo = Boolean(propIsDemo ?? isDemoSession());
  const [policy, setPolicy] = useState<PolicyData | null>(null);
  const [title, setTitle] = useState<string>("");
  const [version, setVersion] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPolicy();
  }, []);

  const loadPolicy = async () => {
    try {
      const data = await fetchActivePolicy();
      setPolicy(data);
      setTitle(data.title || "TruthCart Official Store Policies 2026");
      setVersion(data.version || "v1.1.0");
      setContent(data.content || "");
    } catch (err: any) {
      setError(err.message || "Failed to load active policy");
    }
  };

  const handleSavePolicy = async () => {
    if (!content.trim() || !title.trim()) return;
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      if (isDemo) {
        setSuccessMsg(`[Demo Sandbox Mode] Policy preview updated in demo session memory. Production database is untouched.`);
        return;
      }
      await updatePolicy({
        title: title.trim(),
        version: version.trim() || "v1.1.0",
        content: content.trim(),
      });
      setSuccessMsg(`Store policy version ${version} updated and activated successfully!`);
      await loadPolicy();
    } catch (err: any) {
      setError(err.message || "Failed to update store policy.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <FileText className="h-6 w-6 text-indigo-600" />
            <span>Store Policy Management & Indexing</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Official ground-truth source for returns, shipping fees, warranty terms, and cancellations. TruthCart AI cites these sections directly.
          </p>
        </div>

        <button
          onClick={handleSavePolicy}
          disabled={isSaving}
          className="flex items-center space-x-1.5 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm transition-colors cursor-pointer disabled:opacity-50 shrink-0"
        >
          <Save className="h-4 w-4" />
          <span>{isSaving ? "Saving & Re-indexing..." : "Save & Activate Policy"}</span>
        </button>
      </div>

      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">✕</button>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor Form */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Policy Document Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Document Version</label>
              <input
                type="text"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white font-mono"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-slate-700">Policy Document Content</label>
              <span className="text-[11px] text-slate-400">Use section format: === SECTION: RETURNS ===</span>
            </div>
            <textarea
              rows={16}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full p-4 font-mono text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50/50 text-slate-800 leading-relaxed"
            />
          </div>
        </div>

        {/* Sidebar Info & Section Guidelines */}
        <div className="space-y-4">
          <div className="bg-indigo-50/70 p-5 rounded-2xl border border-indigo-200/80 space-y-3">
            <h4 className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center space-x-1.5">
              <ShieldCheck className="h-4 w-4 text-indigo-600" />
              <span>Section Formatting Syntax</span>
            </h4>
            <p className="text-xs text-indigo-800 leading-relaxed">
              TruthCart AI segments policies into traceable sections using the following delimiter format:
            </p>
            <div className="bg-white/80 p-3 rounded-xl border border-indigo-200 text-[11px] font-mono text-slate-700 space-y-1">
              <div>=== SECTION: RETURNS ===</div>
              <div>Title: Return & Exchange Policy</div>
              <div>Policy ID: POLICY:RETURNS</div>
              <div>Content: Customers may return...</div>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-3">
            <h4 className="text-xs font-bold text-slate-800">Currently Parsed Active Sections</h4>
            {policy?.sections ? (
              <div className="space-y-2">
                {Object.entries(policy.sections).map(([k, s]) => (
                  <div key={k} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs flex items-center justify-between">
                    <div>
                      <strong className="text-slate-800 block">{s.title}</strong>
                      <span className="text-[10px] text-slate-400 font-mono">{s.section_id}</span>
                    </div>
                    <span className="text-[10px] font-bold text-indigo-600 uppercase bg-indigo-50 px-2 py-0.5 rounded">
                      {s.topic}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No active sections parsed.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
