import React, { useState, useEffect, useRef } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Layers,
  Database,
  Tag,
  Cpu,
  FileSpreadsheet,
  Loader2
} from "lucide-react";
import { fetchDemoCatalogueVersions, isDemoSession } from "../services/demoService";
import {
  uploadCataloguePreview,
  confirmCatalogueImport,
  activateCatalogue,
  fetchCatalogueVersions,
  retryDatasetEmbeddings,
  fetchActivationJob,
  retryActivationJob,
  getStoredUser
} from "../services/api";
import type { CataloguePreview, CatalogueVersion, ActivationJob } from "../types";

interface OwnerCatalogueViewProps {
  isDemo?: boolean;
}

const CATEGORY_LABELS: Record<string, { label: string; badgeClass: string }> = {
  PRODUCT_CATALOGUE: { label: "Category A: Product Catalogue", badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  MARKETPLACE_LISTINGS: { label: "Category B: Marketplace Listings", badgeClass: "bg-sky-50 text-sky-700 border-sky-200" },
  COMPETITOR_PRICING: { label: "Category C: Competitor Pricing", badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
  CUSTOMER_REVIEWS: { label: "Category D: Customer Reviews", badgeClass: "bg-purple-50 text-purple-700 border-purple-200" },
  PRODUCT_SPECIFICATIONS: { label: "Category E: Product Specifications", badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  POLICIES_AND_EVIDENCE: { label: "Category F: Policies & Evidence", badgeClass: "bg-slate-50 text-slate-700 border-slate-200" },
  GENERIC_DATASET: { label: "Category G: Generic Market Data", badgeClass: "bg-blue-50 text-blue-700 border-blue-200" }
};

export const OwnerCatalogueView: React.FC<OwnerCatalogueViewProps> = ({ isDemo: propIsDemo }) => {
  const user = getStoredUser();
  const isDemo = Boolean(propIsDemo ?? user?.is_demo ?? isDemoSession());
  const [file, setFile] = useState<File | null>(null);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [isActivating, setIsActivating] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<Record<string, ActivationJob>>({});
  const pollingRef = useRef<Record<string, number>>({});
  const [preview, setPreview] = useState<CataloguePreview | null>(null);
  const [versions, setVersions] = useState<CatalogueVersion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form fields for import confirmation
  const [customName, setCustomName] = useState<string>("");
  const [customVersion, setCustomVersion] = useState<string>("");

  useEffect(() => {
    loadVersions();
    return () => {
      // Clear any active polling timers on unmount
      Object.values(pollingRef.current).forEach((id) => clearInterval(id));
    };
  }, [isDemo]);

  const startJobPolling = (jobId: string, catId: string, version: string) => {
    if (pollingRef.current[catId]) {
      clearInterval(pollingRef.current[catId]);
    }

    const intervalId = window.setInterval(async () => {
      try {
        const job = await fetchActivationJob(jobId);
        setActiveJobs((prev) => ({ ...prev, [catId]: job }));

        if (job.status === "ACTIVE" || job.status === "COMPLETED") {
          clearInterval(pollingRef.current[catId]);
          delete pollingRef.current[catId];
          setIsActivating((prev) => (prev === catId ? null : prev));
          setActiveJobs((prev) => {
            const next = { ...prev };
            delete next[catId];
            return next;
          });
          setSuccessMsg(`Catalogue version ${version} (${job.total_records.toLocaleString()} records) successfully activated and indexed!`);
          await loadVersions();
        } else if (job.status === "FAILED") {
          clearInterval(pollingRef.current[catId]);
          delete pollingRef.current[catId];
          setIsActivating((prev) => (prev === catId ? null : prev));
          setActiveJobs((prev) => {
            const next = { ...prev };
            delete next[catId];
            return next;
          });
          setError(`Activation failed for ${version}: ${job.error_message || "Unknown error"}`);
          await loadVersions();
        }
      } catch (err: any) {
        console.error("Polling error for job", jobId, err);
      }
    }, 1000);

    pollingRef.current[catId] = intervalId;
  };

  const loadVersions = async () => {
    try {
      const data = isDemo ? await fetchDemoCatalogueVersions() : await fetchCatalogueVersions();
      setVersions(data);

      // Auto-resume polling for any in-flight activation jobs (recovers from page reload)
      data.forEach((v) => {
        if (v.active_job_id && (v.job_status === "ACTIVATING" || v.job_status === "INDEXING")) {
          if (!pollingRef.current[v.id]) {
            setIsActivating(v.id);
            startJobPolling(v.active_job_id, v.id, v.version);
          }
        }
      });
    } catch (err: any) {
      console.error("Error loading versions:", err);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setPreview(null);
      setError(null);
      setSuccessMsg(null);
      setSelectedSheet("");
    }
  };

  const handleUploadAndPreview = async (overrideCat?: string, overrideSheet?: string) => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const prev = await uploadCataloguePreview(
        file,
        overrideSheet ?? selectedSheet,
        overrideCat ?? selectedCategory
      );
      setPreview(prev);
      setCustomName(`Import: ${file.name}`);
      setCustomVersion(prev.inferred_version || "v1.1.0");
      if (prev.detected_category && !selectedCategory) {
        setSelectedCategory(prev.detected_category);
      }
      if (prev.available_sheets && prev.available_sheets.length > 0 && !selectedSheet) {
        setSelectedSheet(prev.available_sheets[0]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to parse and validate dataset.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!preview || !file) return;
    if (isDemo) {
      setSuccessMsg(`[Demo Sandbox Mode] Simulated import of '${customVersion || "v1.1.0"}' into demo session memory. Production database is untouched.`);
      setPreview(null);
      setFile(null);
      return;
    }
    setIsImporting(true);
    setError(null);

    try {
      const created = await confirmCatalogueImport({
        name: customName || `Import: ${file.name}`,
        version: customVersion || "v1.1.0",
        filename: file.name,
        records: (preview.all_valid_records && preview.all_valid_records.length > 0) ? preview.all_valid_records : preview.preview_records,
        valid_count: preview.valid_count,
        invalid_count: preview.invalid_count,
        validation_report: { errors: preview.errors, warnings: preview.warnings },
        category: selectedCategory || preview.detected_category || "PRODUCT_CATALOGUE",
        schema_mapping: preview.schema_mappings
      });
      setSuccessMsg(`Dataset ${created.version} successfully imported into database as READY FOR ACTIVATION!`);
      setPreview(null);
      setFile(null);
      await loadVersions();
    } catch (err: any) {
      setError(err.message || "Import failed.");
    } finally {
      setIsImporting(false);
    }
  };

  const handleActivate = async (catId: string, version: string) => {
    if (isDemo) {
      setVersions((prev) => prev.map((v) => ({ ...v, is_active: v.id === catId })));
      setSuccessMsg(`[Demo Sandbox Mode] Version ${version} activated in demo view. Production database is untouched.`);
      return;
    }
    setIsActivating(catId);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await activateCatalogue(catId, true);
      if (res.job_id && (res.status === "ACTIVATING" || res.status === "INDEXING")) {
        startJobPolling(res.job_id, catId, version);
      } else {
        setSuccessMsg(`Catalogue version ${version} is now the active official store truth!`);
        setIsActivating((prev) => (prev === catId ? null : prev));
        await loadVersions();
      }
    } catch (err: any) {
      setError(err.message || "Activation failed.");
      setIsActivating((prev) => (prev === catId ? null : prev));
    }
  };

  const handleRetryJob = async (jobId: string, catId: string, version: string) => {
    try {
      setError(null);
      setIsActivating(catId);
      const res = await retryActivationJob(jobId);
      startJobPolling(res.id, catId, version);
    } catch (err: any) {
      setError(err.message || "Failed to retry activation job.");
      setIsActivating((prev) => (prev === catId ? null : prev));
    }
  };

  const handleRetryEmbeddings = async (catId: string) => {
    try {
      setError(null);
      await retryDatasetEmbeddings(catId);
      setSuccessMsg("Dataset embeddings successfully re-indexed!");
      await loadVersions();
    } catch (err: any) {
      setError(err.message || "Failed to retry embeddings.");
    }
  };

  const currentCategoryInfo = CATEGORY_LABELS[selectedCategory || preview?.detected_category || "PRODUCT_CATALOGUE"] || {
    label: selectedCategory || preview?.detected_category || "General Dataset",
    badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200"
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-8 animate-fade-in">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
          <Layers className="h-6 w-6 text-indigo-600" />
          <span>Universal Dataset Ingestion & Catalogue Management</span>
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Intelligently ingests product catalogues, competitor pricing, marketplace listings, reviews, and specifications. Dynamic schema inference, adaptive embeddings, and atomic version activation.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-600">✕</button>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between font-medium">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-600">✕</button>
        </div>
      )}

      {/* Step 1: Upload Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <span className="h-6 w-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">
              1
            </span>
            <h3 className="text-sm font-bold text-slate-900">Upload & Inspect Dataset</h3>
          </div>
          <span className="text-xs text-slate-400">Supported: .csv, .tsv, .json, .jsonl, .xls, .xlsx (max 35MB)</span>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          <input
            type="file"
            id="catalogue-file-input"
            accept=".csv,.tsv,.json,.jsonl,.xls,.xlsx"
            onChange={handleFileChange}
            className="w-full text-xs text-slate-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
          />

          <button
            onClick={() => handleUploadAndPreview()}
            disabled={!file || isUploading}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm transition-all disabled:opacity-50 cursor-pointer shrink-0"
          >
            {isUploading ? "Profiling & Validating..." : "Upload & Analyze Schema"}
          </button>
        </div>
      </div>

      {/* Step 2: Preview & Validation Report */}
      {preview && (
        <div className="bg-white rounded-2xl p-6 border border-indigo-200 shadow-md space-y-5 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
            <div className="flex items-center space-x-2">
              <span className="h-6 w-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">
                2
              </span>
              <h3 className="text-sm font-bold text-slate-900">
                Profiling Report: {preview.filename}
              </h3>
            </div>
            <div className="flex items-center flex-wrap gap-2 text-xs font-semibold">
              <span className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${currentCategoryInfo.badgeClass}`}>
                {currentCategoryInfo.label}
              </span>
              <span className="text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                {preview.valid_count} Valid Records
              </span>
              {preview.invalid_count > 0 && (
                <span className="text-rose-700 bg-rose-50 px-2.5 py-1 rounded-lg border border-rose-200">
                  {preview.invalid_count} Invalid
                </span>
              )}
            </div>
          </div>

          {/* Metadata & Inferred Category Ribbon */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600">
            <div className="flex items-center space-x-2">
              <Database className="h-4 w-4 text-indigo-500 shrink-0" />
              <span>
                Format: <strong className="text-slate-800">{preview.detected_format || "Tabular"}</strong> ({preview.total_rows} rows)
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Cpu className="h-4 w-4 text-purple-500 shrink-0" />
              <span>
                Embeddings: <strong className={preview.embedding_eligible ? "text-emerald-700 font-semibold" : "text-amber-700"}>
                  {preview.embedding_eligible ? "Eligible (Adaptive Vector)" : "Structured Store Only"}
                </strong>
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Tag className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>
                Confidence: <strong className="text-slate-800">{Math.round((preview.category_confidence ?? 1.0) * 100)}%</strong>
              </span>
            </div>
          </div>

          {/* Category Override & Multi-sheet Selection */}
          <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
            <span className="font-semibold text-slate-700">Category Override:</span>
            <select
              value={selectedCategory || preview.detected_category || ""}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                handleUploadAndPreview(e.target.value, selectedSheet);
              }}
              className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {Object.entries(CATEGORY_LABELS).map(([catKey, catVal]) => (
                <option key={catKey} value={catKey}>{catVal.label}</option>
              ))}
            </select>

            {preview.available_sheets && preview.available_sheets.length > 1 && (
              <div className="flex items-center space-x-2 ml-4">
                <FileSpreadsheet className="h-4 w-4 text-indigo-600" />
                <span className="font-semibold text-slate-700">Workbook Sheet:</span>
                <select
                  value={selectedSheet}
                  onChange={(e) => {
                    setSelectedSheet(e.target.value);
                    handleUploadAndPreview(selectedCategory, e.target.value);
                  }}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  {preview.available_sheets.map((sh) => (
                    <option key={sh} value={sh}>{sh}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Semantic Schema Mappings */}
          {preview.schema_mappings && Object.keys(preview.schema_mappings).length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                Inferred Column Mappings & Inferred Types:
              </span>
              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 bg-slate-50/80 rounded-xl border border-slate-200">
                {Object.entries(preview.schema_mappings).map(([origCol, prof]: [string, any]) => (
                  <span
                    key={origCol}
                    className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[11px] bg-white border border-slate-200 text-slate-700 shadow-2xs font-mono"
                  >
                    <span className="text-slate-500">{origCol}</span>
                    <span className="text-indigo-500 font-bold">→</span>
                    <span className="font-bold text-indigo-700">{prof.mapped_field || "attributes"}</span>
                    <span className="text-[10px] text-slate-400">({prof.inferred_type})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Validation Errors if any */}
          {preview.errors.length > 0 && (
            <div className="p-4 rounded-xl bg-rose-50/80 border border-rose-200 space-y-2">
              <span className="text-xs font-bold text-rose-800 flex items-center space-x-1.5">
                <AlertTriangle className="h-4 w-4 text-rose-600" />
                <span>Detected Row Validation Errors ({preview.errors.length}):</span>
              </span>
              <div className="max-h-36 overflow-y-auto space-y-1 text-[11px] text-rose-700">
                {preview.errors.map((err, idx) => (
                  <div key={idx} className="font-mono bg-white/70 p-1.5 rounded border border-rose-200">
                    Row {err.row} [{err.product_id || err.record_id || "Row"}]: {err.issue}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Record Preview Table */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              Normalized Records Preview (First 10 of {preview.valid_count}):
            </span>
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-semibold">
                  <tr>
                    <th className="py-2 px-3">Identifier</th>
                    <th className="py-2 px-3">Title / Reference</th>
                    <th className="py-2 px-3">Category</th>
                    <th className="py-2 px-3">Price / Value</th>
                    <th className="py-2 px-3">Status / Content</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                  {preview.preview_records.slice(0, 10).map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50/80">
                      <td className="py-2 px-3 font-mono font-semibold text-indigo-700">
                        {r.product_id || r.record_id || `ROW-${i+1}`}
                      </td>
                      <td className="py-2 px-3 truncate max-w-xs">{r.title || r.product_reference || "N/A"}</td>
                      <td className="py-2 px-3">{r.category || r.category_type || "General"}</td>
                      <td className="py-2 px-3 font-semibold">
                        {r.price !== undefined && r.price > 0 ? `₹${Number(r.price).toLocaleString("en-IN")}` : (r.observed_price ? `${r.currency || 'INR'} ${Number(r.observed_price).toLocaleString("en-IN")}` : "—")}
                      </td>
                      <td className="py-2 px-3 truncate max-w-xs text-slate-500">
                        {r.stock_status || (r.rating ? `${r.rating}★` : (r.review_text || r.description || "Active"))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Import Confirmation Form */}
          <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="Dataset Name..."
                className="w-full sm:w-64 px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              />
              <input
                type="text"
                value={customVersion}
                onChange={(e) => setCustomVersion(e.target.value)}
                placeholder="Version (e.g. v1.1.0)"
                className="w-full sm:w-32 px-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white font-mono"
              />
            </div>

            <button
              onClick={handleConfirmImport}
              disabled={isImporting || preview.valid_count === 0}
              className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs shadow-sm transition-all disabled:opacity-50 cursor-pointer shrink-0"
            >
              {isImporting ? "Saving to Database..." : "Confirm Import to Database"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Versions Table */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <span className="h-6 w-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">
              3
            </span>
            <h3 className="text-sm font-bold text-slate-900">Datasets & Active Catalogue Versions</h3>
          </div>
          <span className="text-xs text-slate-400">Atomic Switching • Zero Downtime</span>
        </div>

        {versions.length === 0 ? (
          <p className="text-xs text-slate-400 py-6 text-center">No catalogue versions loaded yet.</p>
        ) : (
          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Version</th>
                  <th className="py-2.5 px-3">Name</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Valid Items</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Created</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {versions.map((v) => (
                  <tr key={v.id} className={v.is_active ? "bg-indigo-50/40" : "hover:bg-slate-50/80"}>
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{v.version}</td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-900">{v.name}</div>
                      <div className="text-slate-400 font-mono text-[10px]">{v.filename}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                        {v.category?.replace(/_/g, " ") || "PRODUCT CATALOGUE"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">{v.valid_count}</td>
                    <td className="py-2.5 px-3">
                      {v.is_active ? (
                        <div className="flex items-center space-x-1.5">
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            <CheckCircle2 className="h-2.5 w-2.5" />
                            <span>ACTIVE</span>
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-sky-50 text-sky-700">
                            INDEXED
                          </span>
                        </div>
                      ) : (activeJobs[v.id] || isActivating === v.id || (v.active_job_id && (v.job_status === "ACTIVATING" || v.job_status === "INDEXING"))) ? (
                        <div className="space-y-1 min-w-[150px]">
                          <div className="flex items-center justify-between text-[10px] font-medium text-indigo-700">
                            <span className="flex items-center space-x-1">
                              <Loader2 className="h-3 w-3 animate-spin text-indigo-600 shrink-0" />
                              <span className="truncate max-w-[90px]">{activeJobs[v.id]?.stage?.replace(/_/g, " ") || v.job_stage?.replace(/_/g, " ") || "Activating"}</span>
                            </span>
                            <span className="font-mono text-[9px]">{Math.round(activeJobs[v.id]?.progress_percent ?? v.progress_percent ?? 0)}%</span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-indigo-600 h-1.5 transition-all duration-300 rounded-full"
                              style={{ width: `${Math.max(8, activeJobs[v.id]?.progress_percent ?? v.progress_percent ?? 0)}%` }}
                            />
                          </div>
                          <div className="text-[9px] text-slate-400 font-mono">
                            {activeJobs[v.id] ? `${activeJobs[v.id].processed_records} / ${activeJobs[v.id].total_records}` : `${v.processed_records || 0} / ${v.total_records || v.valid_count}`} items
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-1.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            v.status === "FAILED" || v.job_status === "FAILED" ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-600"
                          }`}>
                            {v.status === "INDEX_BUILDING" ? "ACTIVATING" : v.status}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold ${
                            v.embedding_status === "INDEXED" ? "bg-sky-50 text-sky-700" :
                            v.embedding_status === "EMBEDDING_FAILED" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700"
                          }`}>
                            {v.embedding_status || "INDEXED"}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                      {new Date(v.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 px-3 text-right space-x-2">
                      {v.embedding_status === "EMBEDDING_FAILED" && (
                        <button
                          onClick={() => handleRetryEmbeddings(v.id)}
                          className="px-2 py-0.5 rounded bg-amber-100 hover:bg-amber-200 text-amber-800 text-[10px] font-semibold cursor-pointer"
                        >
                          Retry Index
                        </button>
                      )}
                      {v.is_active ? (
                        <span className="text-[11px] font-bold text-emerald-600">Currently Live</span>
                      ) : (activeJobs[v.id] || isActivating === v.id || (v.active_job_id && (v.job_status === "ACTIVATING" || v.job_status === "INDEXING"))) ? (
                        <span className="inline-flex items-center space-x-1.5 text-[11px] font-semibold text-indigo-600 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                          <span>Activating...</span>
                        </span>
                      ) : (activeJobs[v.id]?.status === "FAILED" || v.status === "FAILED" || v.job_status === "FAILED" || v.status === "INDEX_BUILDING") ? (
                        <button
                          onClick={() => v.active_job_id ? handleRetryJob(v.active_job_id, v.id, v.version) : handleActivate(v.id, v.version)}
                          className="px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-[11px] transition-colors shadow-xs cursor-pointer"
                        >
                          Retry Activation
                        </button>
                      ) : (
                        <button
                          onClick={() => handleActivate(v.id, v.version)}
                          disabled={Boolean(isActivating) || Boolean(activeJobs[v.id])}
                          className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-[11px] transition-colors shadow-xs cursor-pointer disabled:opacity-50"
                        >
                          Activate Version
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
