import React from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, Sparkles, FolderDown } from "lucide-react";
import type { CatalogueStatusResponse } from "../types";

interface ReadinessBannerProps {
  catalogueStatus: CatalogueStatusResponse | null;
  onToggleFixtures: (enable: boolean) => void;
  isLoading: boolean;
}

export const ReadinessBanner: React.FC<ReadinessBannerProps> = ({
  catalogueStatus,
  onToggleFixtures,
  isLoading,
}) => {
  if (!catalogueStatus) return null;

  const isOfficial = catalogueStatus.is_official;
  const isSynthetic = catalogueStatus.is_synthetic_fixture;

  if (isOfficial) {
    return (
      <div className="bg-emerald-50 border-b border-emerald-200 px-4 py-2 text-xs text-emerald-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>
            <strong>Official Hackathon Catalogue Active:</strong>{" "}
            {catalogueStatus.records_loaded} items loaded. Ground truth evidence verification active.
          </span>
        </div>
      </div>
    );
  }

  if (isSynthetic) {
    return (
      <div className="bg-indigo-50/80 border-b border-indigo-100 px-4 py-2.5 text-xs text-indigo-900 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-4 w-4 text-indigo-600 shrink-0" />
          <span>
            <strong>Development Fixture Mode:</strong> Using isolated synthetic development fixtures ({catalogueStatus.records_loaded} items) for local pipeline validation. Organiser catalogue directory (`data/products/`) is currently awaiting official files.
          </span>
        </div>
        <button
          onClick={() => onToggleFixtures(false)}
          disabled={isLoading}
          className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-white hover:bg-slate-50 text-indigo-700 border border-indigo-200 transition-colors shadow-2xs cursor-pointer"
        >
          Switch to Strict "Awaiting Catalogue" Mode
        </button>
      </div>
    );
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-3 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-start sm:items-center space-x-2.5">
        <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
        <div>
          <span className="font-semibold text-amber-950">Awaiting Official Organiser Catalogue:</span>{" "}
          Place the hackathon product dataset (CSV or JSON) in <code className="bg-amber-100 px-1 py-0.5 rounded text-amber-950">data/products/</code> to activate live catalogue answering.
        </div>
      </div>
      <div className="flex items-center space-x-2">
        <button
          onClick={() => onToggleFixtures(true)}
          disabled={isLoading}
          className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white shadow-2xs transition-colors flex items-center space-x-1 cursor-pointer"
        >
          {isLoading ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <FolderDown className="h-3.5 w-3.5 mr-1" />
          )}
          Load Development Fixtures for Testing
        </button>
      </div>
    </div>
  );
};
