import type {
  HealthResponse,
  CatalogueStatusResponse,
  ActivationJob,
  EvaluationReportResponse,
  AuthResponse,
  User,
  CatalogueVersion,
  CataloguePreview,
  ProductItem,
  FeedbackItem,
  PolicyData,
  AuditLog,
  SystemStats,
} from "../types";

function isLocalHostname(hostname: string): boolean {
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1") {
    return true;
  }
  return (
    /^192\.168\.\d{1,3}\.\d{1,3}$/.test(hostname) ||
    /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname) ||
    /^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(hostname) ||
    hostname.endsWith(".local") ||
    hostname.includes("devtunnels.ms") ||
    hostname.includes("ngrok") ||
    hostname.includes("loca.lt")
  );
}

function getApiBase(): string {
  const envBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
  const isLocal =
    typeof window !== "undefined" &&
    (isLocalHostname(window.location.hostname) ||
      window.location.port === "5173" ||
      window.location.port === "3000");

  // If valid custom URL is configured and NOT a dummy placeholder containing 'xxxx', use it
  if (envBase && !envBase.includes("xxxx")) {
    const cleaned = envBase.replace(/\/+$/, "");
    return cleaned.endsWith("/api") ? cleaned : `${cleaned}/api`;
  }

  // On local development, route through local Vite proxy (/api -> http://127.0.0.1:8000)
  if (isLocal) {
    return "/api";
  }

  // In production (Vercel), default directly to verified live new Render backend
  return "https://truthcart-ai-updated.onrender.com/api";
}

export const API_BASE = getApiBase();

function handleFetchError(err: any, _fallbackMessage?: string): never {
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    throw new Error(
      "Unable to connect to the TruthCart server. The cloud backend may be spinning up (Render free tier takes ~30s on cold start). Please wait a few moments and try again."
    );
  }
  throw err;
}

// Local token management
export function getStoredToken(): string | null {
  return localStorage.getItem("truthcart_token");
}

export function setStoredToken(token: string): void {
  localStorage.setItem("truthcart_token", token);
}

export function clearStoredToken(): void {
  localStorage.removeItem("truthcart_token");
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem("truthcart_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(user: User): void {
  localStorage.setItem("truthcart_user", JSON.stringify(user));
}

export function clearStoredUser(): void {
  localStorage.removeItem("truthcart_user");
}

function getAuthHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ================= AUTHENTICATION =================
export async function signup(fullName: string, email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: fullName, email, password }),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Signup failed. Please verify your details.");
    }
    const data: AuthResponse = await res.json();
    setStoredToken(data.access_token);
    setStoredUser(data.user);
    return data;
  } catch (err: any) {
    handleFetchError(err, "Signup failed");
  }
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Login failed. Invalid email or password.");
    }
    const data: AuthResponse = await res.json();
    setStoredToken(data.access_token);
    setStoredUser(data.user);
    return data;
  } catch (err: any) {
    handleFetchError(err, "Login failed");
  }
}

export async function ownerLogin(email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/owner-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Owner login failed. Invalid credentials.");
    }
    const data: AuthResponse = await res.json();
    setStoredToken(data.access_token);
    setStoredUser(data.user);
    return data;
  } catch (err: any) {
    handleFetchError(err, "Owner login failed");
  }
}

export async function createDemoSession(role: "CUSTOMER" | "OWNER"): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/demo-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || "Demo session initialization failed");
    }
    const data: AuthResponse = await res.json();
    setStoredToken(data.access_token);
    setStoredUser(data.user);
    return data;
  } catch (err: any) {
    handleFetchError(err, "Demo session initialization failed");
  }
}

export async function fetchMe(): Promise<User> {
  const token = getStoredToken();
  if (!token) {
    throw new Error("No active session token");
  }
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    clearStoredToken();
    clearStoredUser();
    throw new Error("Failed to authenticate session");
  }
  const user = await res.json();
  setStoredUser(user);
  return user;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: getAuthHeaders(),
    });
  } catch {
    // Ignore network error on logout
  } finally {
    clearStoredToken();
    clearStoredUser();
  }
}

// ================= SYSTEM HEALTH & READINESS =================
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSystemStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/system/stats`);
  if (!res.ok) {
    throw new Error(`Stats fetch failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDetailedReadiness(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/system/readiness`);
  if (!res.ok) {
    throw new Error(`Readiness fetch failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAuditLogs(limit: number = 50): Promise<AuditLog[]> {
  const res = await fetch(`${API_BASE}/audit-logs?limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to load audit logs");
  }
  return res.json();
}

// ================= CATALOGUE MANAGEMENT =================
export async function fetchCatalogueStatus(): Promise<CatalogueStatusResponse> {
  const res = await fetch(`${API_BASE}/catalogue/status`);
  if (!res.ok) {
    throw new Error(`Catalogue status fetch failed: ${res.statusText}`);
  }
  return res.json();
}

export async function reloadCatalogue(useSynthetic: boolean = false): Promise<CatalogueStatusResponse> {
  const res = await fetch(`${API_BASE}/catalogue/reload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_synthetic: useSynthetic }),
  });
  if (!res.ok) {
    throw new Error(`Catalogue reload failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchCatalogueVersions(): Promise<CatalogueVersion[]> {
  const res = await fetch(`${API_BASE}/catalogue/versions`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to fetch versions");
  }
  return res.json();
}

export async function uploadCataloguePreview(
  file: File,
  sheet?: string,
  categoryOverride?: string
): Promise<CataloguePreview> {
  const formData = new FormData();
  formData.append("file", file);
  if (sheet) formData.append("sheet", sheet);
  if (categoryOverride) formData.append("category_override", categoryOverride);

  const token = getStoredToken();
  const headers: HeadersInit = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/catalogue/upload-preview`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to parse and validate dataset file");
  }
  return res.json();
}

export async function confirmCatalogueImport(params: {
  name: string;
  version: string;
  filename: string;
  records: any[];
  valid_count: number;
  invalid_count: number;
  validation_report?: any;
  category?: string;
  schema_mapping?: any;
}): Promise<CatalogueVersion> {
  const res = await fetch(`${API_BASE}/catalogue/import`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Catalogue import confirmation failed");
  }
  return res.json();
}

export async function activateCatalogue(catId: string, asyncMode: boolean = true): Promise<CatalogueStatusResponse> {
  const res = await fetch(`${API_BASE}/catalogue/${catId}/activate?async_mode=${asyncMode}`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Catalogue activation failed");
  }
  return res.json();
}

export async function fetchActivationJob(jobId: string): Promise<ActivationJob> {
  const res = await fetch(`${API_BASE}/catalogue/jobs/${jobId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to fetch activation job status");
  }
  return res.json();
}

export async function fetchDatasetActivationStatus(catId: string): Promise<ActivationJob | null> {
  const res = await fetch(`${API_BASE}/catalogue/${catId}/activation-status`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    return null;
  }
  return res.json();
}

export async function retryActivationJob(jobId: string): Promise<ActivationJob> {
  const res = await fetch(`${API_BASE}/catalogue/jobs/${jobId}/retry`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to retry activation job");
  }
  return res.json();
}

export async function rebuildKnowledgeBaseIndex(): Promise<any> {
  const res = await fetch(`${API_BASE}/catalogue/rebuild-index`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Index rebuild failed");
  }
  return res.json();
}

export async function retryDatasetEmbeddings(datasetId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/catalogue/${datasetId}/retry-embeddings`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Retry embeddings failed");
  }
  return res.json();
}

// ================= PRODUCT BROWSE & EDIT =================
export async function fetchProducts(params: {
  category?: string;
  min_price?: number;
  max_price?: number;
  in_stock_only?: boolean;
  search?: string;
  sort_by?: string;
  limit?: number;
  offset?: number;
  demo?: boolean;
}): Promise<{
  total: number;
  categories: string[];
  products: ProductItem[];
  page?: number;
  total_pages?: number;
  has_next?: boolean;
  has_prev?: boolean;
}> {
  const query = new URLSearchParams();
  if (params.category) query.append("category", params.category);
  if (params.min_price !== undefined) query.append("min_price", String(params.min_price));
  if (params.max_price !== undefined) query.append("max_price", String(params.max_price));
  if (params.in_stock_only) query.append("in_stock_only", "true");
  if (params.search) query.append("search", params.search);
  if (params.sort_by) query.append("sort_by", params.sort_by);
  if (params.limit) query.append("limit", String(params.limit));
  if (params.offset !== undefined) query.append("offset", String(params.offset));
  if (params.demo !== undefined) {
    if (params.demo) query.append("demo", "true");
  }

  const res = await fetch(`${API_BASE}/products?${query.toString()}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error("Failed to load products");
  }
  return res.json();
}

export async function fetchProduct(productId: string): Promise<ProductItem> {
  const res = await fetch(`${API_BASE}/products/${encodeURIComponent(productId)}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Product ${productId} not found`);
  }
  return res.json();
}

export async function addProduct(productData: Partial<ProductItem>): Promise<ProductItem> {
  const res = await fetch(`${API_BASE}/products`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(productData),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Product creation failed");
  }
  return res.json();
}

export async function updateProductVerified(
  productId: string,
  updates: Partial<ProductItem>
): Promise<any> {
  const res = await fetch(`${API_BASE}/products/${encodeURIComponent(productId)}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Product update failed");
  }
  return res.json();
}

export async function archiveProduct(productId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/products/${encodeURIComponent(productId)}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Product archive failed");
  }
  return res.json();
}

// ================= CUSTOMER CHAT =================
export async function sendChatMessage(
  message: string,
  conversationId?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Chat request failed: ${res.statusText}`);
  }
  return res.json();
}

// ================= CUSTOMER FEEDBACK & REVIEW =================
export async function submitFeedback(params: {
  feedback_type: string;
  message: string;
  product_id?: string;
  conversation_id?: string;
  rating?: number;
}): Promise<FeedbackItem> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Feedback submission failed");
  }
  return res.json();
}

export async function fetchMyFeedback(): Promise<FeedbackItem[]> {
  const res = await fetch(`${API_BASE}/feedback/my`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to load feedback history");
  }
  return res.json();
}

export async function fetchOwnerFeedback(params?: {
  status?: string;
  type?: string;
  product_id?: string;
}): Promise<FeedbackItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.type) query.append("type", params.type);
  if (params?.product_id) query.append("product_id", params.product_id);

  const res = await fetch(`${API_BASE}/feedback/owner?${query.toString()}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to load owner feedback");
  }
  return res.json();
}

export async function updateFeedbackStatus(
  feedbackId: string,
  status: string,
  resolutionNote?: string
): Promise<FeedbackItem> {
  const res = await fetch(`${API_BASE}/feedback/${feedbackId}/status`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify({ status, resolution_note: resolutionNote }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to update feedback status");
  }
  return res.json();
}

export async function applyVerifiedCorrection(params: {
  feedback_id: string;
  product_id: string;
  updates: Partial<ProductItem>;
  resolution_note: string;
}): Promise<FeedbackItem> {
  const res = await fetch(`${API_BASE}/feedback/verified-correction`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to apply verified correction");
  }
  return res.json();
}

// ================= POLICY MANAGEMENT =================
export async function fetchActivePolicy(): Promise<PolicyData> {
  const res = await fetch(`${API_BASE}/policies/active`);
  if (!res.ok) {
    throw new Error("Failed to load store policies");
  }
  return res.json();
}

export async function updatePolicy(params: {
  title: string;
  content: string;
  version: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/policies/update`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Policy update failed");
  }
  return res.json();
}

// ================= EVALUATION =================
export async function runEvaluationSuite(
  datasetName: string = "sample_eval_questions.json",
  maxQuestions?: number,
  dryRun: boolean = false
): Promise<EvaluationReportResponse> {
  const res = await fetch(`${API_BASE}/evaluation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_name: datasetName,
      max_questions: maxQuestions,
      dry_run: dryRun,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Evaluation run failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchLatestEvaluation(): Promise<any> {
  const res = await fetch(`${API_BASE}/evaluation/latest`);
  if (!res.ok) {
    throw new Error("Failed to fetch latest evaluation");
  }
  return res.json();
}

// ================= CATALOGUE DIAGNOSTICS & REPAIR =================
export async function fetchCatalogueDiagnostics(): Promise<{
  has_active_catalogue: boolean;
  status: string;
  active_catalogue?: {
    id: string;
    name: string;
    version: string;
    category: string;
    filename?: string;
    activated_at?: string;
  };
  total_db_products: number;
  total_eligible_products: number;
  total_archived_products: number;
  total_loader_products: number;
  total_indexed_documents: number;
  is_indexed: boolean;
  missing_from_loader_count: number;
  sample_first?: any;
  sample_last?: any;
}> {
  const res = await fetch(`${API_BASE}/catalogue/diagnostics`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error("Failed to fetch catalogue diagnostics");
  }
  return res.json();
}

export async function repairCatalogueIndex(): Promise<{
  status: string;
  message: string;
  diagnostics: any;
  test_retrieval_ok: boolean;
}> {
  const res = await fetch(`${API_BASE}/catalogue/repair-index`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to repair catalogue index");
  }
  return res.json();
}
