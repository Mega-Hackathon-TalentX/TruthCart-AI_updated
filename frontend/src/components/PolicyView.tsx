import React, { useState, useEffect } from "react";
import { FileText, Shield, RotateCcw, Truck, Award, Ban } from "lucide-react";
import { fetchActivePolicy } from "../services/api";
import type { PolicyData } from "../types";

export const PolicyView: React.FC = () => {
  const [policy, setPolicy] = useState<PolicyData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    loadPolicy();
  }, []);

  const loadPolicy = async () => {
    setIsLoading(true);
    try {
      const data = await fetchActivePolicy();
      setPolicy(data);
    } catch (err) {
      console.error("Failed to load policy:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const getTopicIcon = (topic: string) => {
    switch (topic?.toUpperCase()) {
      case "RETURNS":
        return <RotateCcw className="h-5 w-5 text-indigo-600" />;
      case "SHIPPING":
        return <Truck className="h-5 w-5 text-blue-600" />;
      case "WARRANTY":
        return <Award className="h-5 w-5 text-emerald-600" />;
      case "CANCELLATIONS":
        return <Ban className="h-5 w-5 text-rose-600" />;
      default:
        return <Shield className="h-5 w-5 text-slate-600" />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-in">
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
            <FileText className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              {policy?.title || "Official Store Policies"}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Version: <strong className="text-indigo-600">{policy?.version || "v1.0.0"}</strong> • Ground Truth Source for TruthCart AI Policy Responses
            </p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Loading active store policies...</div>
      ) : !policy?.sections || Object.keys(policy.sections).length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 text-slate-400 text-xs">
          No active policy document configured.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(policy.sections).map(([secId, sec]) => (
            <div
              key={secId}
              className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs space-y-3 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getTopicIcon(sec.topic)}
                    <h3 className="text-sm font-bold text-slate-900">{sec.title}</h3>
                  </div>
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    {sec.section_id}
                  </span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pt-1">
                  {sec.content}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Topic: {sec.topic}</span>
                <span className="text-emerald-600">Active Ground Truth</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
