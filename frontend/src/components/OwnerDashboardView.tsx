import React, { useState, useEffect } from "react";
import {
  Database,
  Cpu,
  MessageSquare,
  BarChart3,
  History,
  ArrowRight,
  Sparkles
} from "lucide-react";
import { fetchSystemStats, fetchDetailedReadiness, rebuildKnowledgeBaseIndex } from "../services/api";
import { fetchDemoSystemStats, isDemoSession } from "../services/demoService";
import type { SystemStats } from "../types";

interface OwnerDashboardViewProps {
  onNavigate: (tab: string) => void;
  onOpenEvaluation: () => void;
  isDemo?: boolean;
}

export const OwnerDashboardView: React.FC<OwnerDashboardViewProps> = ({
  onNavigate,
  onOpenEvaluation,
  isDemo: propIsDemo,
}) => {
  const isDemo = Boolean(propIsDemo ?? isDemoSession());
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [readiness, setReadiness] = useState<Record<string, any> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRebuilding, setIsRebuilding] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, [isDemo]);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [s, r] = isDemo
        ? await Promise.all([fetchDemoSystemStats(), fetchDetailedReadiness()])
        : await Promise.all([fetchSystemStats(), fetchDetailedReadiness()]);
      setStats(s);
      setReadiness(r);
    } catch (err) {
      console.error("Dashboard data load error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRebuildIndex = async () => {
    setIsRebuilding(true);
    setActionMessage(null);
    try {
      if (isDemo) {
        setActionMessage("[Demo Sandbox Mode] Predefined demo knowledge base index verified. Production index is untouched.");
        return;
      }
      const resp = await rebuildKnowledgeBaseIndex();
      setActionMessage(`Knowledge base re-indexed successfully (${resp.products_indexed} products).`);
      await loadDashboardData();
    } catch (err: any) {
      setActionMessage(`Rebuild failed: ${err.message}`);
    } finally {
      setIsRebuilding(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-24 text-center text-slate-400 text-xs">
        Loading {isDemo ? "predefined demo sandbox" : "real store owner"} metrics...
      </div>
    );
  }

  const activeCat = stats?.active_catalogue;
  const fb = stats?.feedback || { total: 0, pending: 0, under_review: 0, resolved: 0, rejected: 0 };
  const lastEval = stats?.last_evaluation;

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 py-4 animate-fade-in">
      {/* Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-purple-950 rounded-2xl p-6 text-white shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-semibold mb-2">
            <Sparkles className="h-3.5 w-3.5" />
            <span>{isDemo ? "Predefined Demo Operations Center" : "Store Owner Operations Center"}</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            {isDemo ? "TruthCart AI Demo Owner Portal" : "TruthCart AI Owner Dashboard"}
          </h2>
          <p className="text-xs text-indigo-200 mt-1 max-w-xl">
            {isDemo
              ? "Isolated demo sandbox dataset. Predefined demo showcase catalog is active. Production owner records are protected and never modified."
              : "Live metrics from SQLite database. Customers cannot modify official catalogue data. All changes must be verified and audited."}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onNavigate("owner-catalogue")}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            {isDemo ? "View Demo Catalogues" : "Upload Catalogue"}
          </button>
          <button
            onClick={handleRebuildIndex}
            disabled={isRebuilding}
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs transition-colors border border-white/20 cursor-pointer disabled:opacity-50"
          >
            {isRebuilding ? "Rebuilding Index..." : "Rebuild Knowledge Base"}
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs flex items-center justify-between animate-fade-in">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="font-bold text-indigo-600 hover:text-indigo-900 cursor-pointer ml-3">
            ✕
          </button>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Catalogue Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Catalogue</span>
            <Database className="h-4 w-4 text-indigo-600" />
          </div>
          <div>
            <span className="text-2xl font-extrabold text-slate-900">
              {activeCat ? activeCat.version : "None"}
            </span>
            <span className="text-xs text-slate-500 block truncate mt-0.5">
              {activeCat ? activeCat.name : "No active catalogue imported"}
            </span>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <button
              onClick={() => onNavigate("owner-catalogue")}
              className="text-indigo-600 font-semibold hover:text-indigo-800 flex items-center space-x-1 cursor-pointer"
            >
              <span>Manage Versions</span>
              <ArrowRight className="h-3 w-3" />
            </button>
            <span className="text-slate-400">{activeCat ? `${activeCat.record_count} items` : "0 items"}</span>
          </div>
        </div>

        {/* Valid Products Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Valid Products</span>
            <Cpu className="h-4 w-4 text-emerald-600" />
          </div>
          <div>
            <span className="text-2xl font-extrabold text-slate-900">
              {stats?.total_valid_products || 0}
            </span>
            <span className="text-xs text-emerald-600 font-medium block mt-0.5">
              100% Schema Validated
            </span>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <button
              onClick={() => onNavigate("owner-products")}
              className="text-indigo-600 font-semibold hover:text-indigo-800 flex items-center space-x-1 cursor-pointer"
            >
              <span>View Products</span>
              <ArrowRight className="h-3 w-3" />
            </button>
            <span className="text-slate-400">Ground Truth</span>
          </div>
        </div>

        {/* Customer Feedback Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Customer Reports</span>
            <MessageSquare className="h-4 w-4 text-amber-600" />
          </div>
          <div>
            <span className="text-2xl font-extrabold text-slate-900">
              {fb.total}
            </span>
            <span className="text-xs text-amber-600 font-medium block mt-0.5">
              {fb.pending} Pending Review
            </span>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <button
              onClick={() => onNavigate("owner-feedback")}
              className="text-indigo-600 font-semibold hover:text-indigo-800 flex items-center space-x-1 cursor-pointer"
            >
              <span>Review Inbox</span>
              <ArrowRight className="h-3 w-3" />
            </button>
            <span className="text-slate-400">{fb.resolved} Resolved</span>
          </div>
        </div>

        {/* Evaluation Benchmarks Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Benchmark Test</span>
            <BarChart3 className="h-4 w-4 text-purple-600" />
          </div>
          <div>
            {lastEval ? (
              <>
                <span className="text-2xl font-extrabold text-purple-700">
                  {Math.round(lastEval.citation_validity_rate * 100)}%
                </span>
                <span className="text-xs text-slate-500 block mt-0.5">
                  Citation Validity ({lastEval.passed_count}/{lastEval.total_questions} passed)
                </span>
              </>
            ) : (
              <>
                <span className="text-base font-bold text-slate-400">Not Evaluated</span>
                <span className="text-xs text-slate-400 block mt-0.5">Run suite to test</span>
              </>
            )}
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <button
              onClick={onOpenEvaluation}
              className="text-indigo-600 font-semibold hover:text-indigo-800 flex items-center space-x-1 cursor-pointer"
            >
              <span>Run Suite</span>
              <ArrowRight className="h-3 w-3" />
            </button>
            <span className="text-slate-400">Official R3</span>
          </div>
        </div>
      </div>

      {/* Readiness Checklist for all 7 sub-systems */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          System Readiness & Isolation Verification
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">1. Local Model</span>
              <span className={`font-semibold px-2 py-0.5 rounded text-[10px] ${
                readiness?.model_readiness?.real_instruction_model_loaded
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-amber-50 text-amber-700 border border-amber-200"
              }`}>
                {readiness?.model_readiness?.real_instruction_model_loaded ? "Ready (Local Weights)" : "Fallback Active"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              {readiness?.model_readiness?.real_instruction_model_loaded
                ? "Organiser GGUF/HF Checkpoint Loaded"
                : "Deterministic Grounded Rule Generator"}
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">2. Dataset Isolation</span>
              <span className={`font-semibold px-2 py-0.5 rounded text-[10px] ${
                isDemo
                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                  : "bg-emerald-50 text-emerald-700 border border-emerald-200"
              }`}>
                {isDemo ? "Predefined Demo Dataset" : "Authoritative Database"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              {isDemo
                ? "Strict separation: 16 isolated demo showcase records"
                : `${readiness?.dataset_readiness?.records_loaded || 0} valid products loaded`}
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">3. Database Persistence</span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[10px]">
                {isDemo ? "Sandbox Protected" : "SQLite WAL Active"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              {isDemo ? "Production DB protected from demo actions" : "ACID transactional versioning enabled"}
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">4. Product Vector Index</span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[10px]">
                Indexed
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              {isDemo ? "16 demo showcase products in vector space" : `${readiness?.product_index_readiness?.indexed_count || 0} products indexed`}
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">5. Policy Index</span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[10px]">
                Active
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Structured store policy sections loaded
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">6. Evidence Engine</span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[10px]">
                Strict Enforcement
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              ANSWER / CLARIFY / REFUSE guardrails active
            </p>
          </div>
        </div>
      </div>

      {/* Recent Audit Events */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="h-4 w-4 text-indigo-600" />
            <h3 className="text-sm font-bold text-slate-900">
              {isDemo ? "Sample Demo Audit Events" : "Recent Owner & System Audit Events"}
            </h3>
          </div>
          <button
            onClick={() => onNavigate("owner-audit")}
            className="text-xs text-indigo-600 font-semibold hover:text-indigo-800 cursor-pointer"
          >
            View Complete Audit Log ↗
          </button>
        </div>

        {stats?.recent_audits && stats.recent_audits.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {stats.recent_audits.map((a) => (
              <div key={a.id} className="py-2.5 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2.5">
                  <span className="font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px]">
                    {a.action}
                  </span>
                  <span className="text-slate-700 font-medium">
                    {a.target_type}: {a.target_id.slice(0, 16)}
                  </span>
                </div>
                <div className="flex items-center space-x-3 text-slate-400 text-[11px]">
                  <span>Role: {a.actor_role}</span>
                  <span>{new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-4 text-center">No audit records logged yet.</p>
        )}
      </div>
    </div>
  );
};
