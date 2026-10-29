import React, { useState, useEffect } from "react";
import { History, RefreshCw } from "lucide-react";
import { fetchAuditLogs } from "../services/api";
import type { AuditLog } from "../types";

export const OwnerAuditView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const data = await fetchAuditLogs(100);
      setLogs(data);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <History className="h-6 w-6 text-indigo-600" />
            <span>Immutable Audit Trail & Operations Log</span>
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Chronological, immutable audit record of catalogue uploads, activations, verified product corrections, policy updates, and feedback resolutions.
          </p>
        </div>

        <button
          onClick={loadLogs}
          className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {isLoading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Loading audit trail records...</div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-400 text-xs">
          No audit records logged yet.
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Target Type</th>
                  <th className="py-3 px-4">Target ID</th>
                  <th className="py-3 px-4">Details Diff / Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {logs.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50/80">
                    <td className="py-3 px-4 text-slate-500 whitespace-nowrap text-[11px]">
                      {new Date(l.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-indigo-700 text-[11px]">
                      {l.action}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        l.actor_role === "OWNER"
                          ? "bg-purple-100 text-purple-800"
                          : l.actor_role === "CUSTOMER"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-slate-100 text-slate-700"
                      }`}>
                        {l.actor_role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-600 uppercase text-[11px] font-semibold">{l.target_type}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500">{l.target_id.slice(0, 10)}...</td>
                    <td className="py-3 px-4 max-w-sm truncate text-[11px] font-mono text-slate-600">
                      {l.details ? JSON.stringify(l.details) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
