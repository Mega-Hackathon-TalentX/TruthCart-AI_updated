export type DecisionType = "ANSWER" | "CLARIFY" | "REFUSE";
export type UserRole = "CUSTOMER" | "OWNER";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_demo?: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface EvidenceItem {
  source_type: "product" | "policy";
  source_id: string;
  field: string;
  value: any;
  confidence: number;
}

export interface EvidenceObject {
  decision: DecisionType;
  query: string;
  evidence: EvidenceItem[];
  unsupported_fields: string[];
  clarification_question?: string | null;
  refusal_reason?: string | null;
}

export interface ProductResult {
  product_id: string;
  title: string;
  description: string;
  category: string;
  price: number;
  stock_status: string;
  rating?: number | null;
  attributes: Record<string, any>;
  citation: string;
}

export interface ComparisonData {
  products: string[];
  product_titles: Record<string, string>;
  dimensions: Record<string, Record<string, any>>;
  notes?: string[];
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  timestamp: string;
  text: string;
  decision?: DecisionType;
  products?: ProductResult[];
  comparison_data?: ComparisonData | null;
  citations?: string[];
  evidence?: EvidenceObject;
  clarification_question?: string | null;
  refusal_reason?: string | null;
  retrieval_status?: string;
  model_status?: string;
  latency_ms?: number;
  token_cost?: number;
}

export interface ReadinessStatus {
  catalogue_ready: boolean;
  policy_ready: boolean;
  embedding_model_ready: boolean;
  instruction_model_ready: boolean;
  is_using_synthetic_fixtures: boolean;
  message: string;
}

export interface HealthResponse {
  status: string;
  project_name: string;
  team_name: string;
  version: string;
  data_readiness: ReadinessStatus;
  model_readiness: {
    embedding_model_ready: boolean;
    instruction_model_ready: boolean;
    embedding_model_type: string;
    instruction_model_type: string;
    execution_mode: string;
    external_api_calls_enabled: boolean;
  };
}

export interface CatalogueStatusResponse {
  status: string;
  is_ready?: boolean;
  is_official: boolean;
  is_synthetic_fixture: boolean;
  records_loaded: number;
  records_rejected: number;
  duplicate_records: number;
  missing_fields_count: number;
  categories: string[];
  total_active_products: number;
  data_source_path?: string | null;
  job_id?: string | null;
  stage?: string | null;
  progress_percent?: number | null;
  total_records?: number | null;
  processed_records?: number | null;
  message?: string | null;
}

export interface ActivationJob {
  id: string;
  dataset_id: string;
  version: string;
  status: "PENDING" | "ACTIVATING" | "PROCESSING_EMBEDDINGS" | "INDEXING" | "ACTIVE" | "PARTIALLY_FAILED" | "FAILED" | "CANCELLED" | string;
  stage: "VALIDATING" | "BATCHING_EMBEDDINGS" | "INDEXING" | "ATOMIC_ACTIVATION" | "COMPLETED" | "FAILED" | string;
  total_records: number;
  processed_records: number;
  embedded_records: number;
  indexed_records: number;
  failed_records: number;
  skipped_records: number;
  current_batch: number;
  total_batches: number;
  batch_size: number;
  progress_percent: number;
  error_message?: string | null;
  error_category?: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  is_active: boolean;
  message?: string | null;
}

export interface CatalogueVersion {
  id: string;
  version: string;
  name: string;
  filename: string;
  owner_id: string;
  record_count: number;
  valid_count: number;
  invalid_count: number;
  status: string;
  is_active: boolean;
  created_at: string;
  activated_at?: string | null;
  category?: string;
  embedding_status?: string;
  active_job_id?: string | null;
  job_status?: string | null;
  job_stage?: string | null;
  processed_records?: number | null;
  total_records?: number | null;
  progress_percent?: number | null;
  job_error?: string | null;
}

export interface CataloguePreview {
  filename: string;
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  preview_records: any[];
  all_valid_records?: any[];
  errors: Array<{ row: number; product_id?: string; record_id?: string; issue: string }>;
  warnings: string[];
  inferred_version: string;
  detected_category?: string;
  category_confidence?: number;
  detected_format?: string;
  available_sheets?: string[];
  embedding_eligible?: boolean;
  schema_mappings?: Record<string, any>;
}

export interface ProductItem {
  id?: string;
  product_id: string;
  title: string;
  description: string;
  category: string;
  price: number;
  stock_status: string;
  rating?: number | null;
  attributes?: Record<string, any>;
  is_archived?: number | boolean;
  created_at?: string;
  updated_at?: string;
}

export interface FeedbackItem {
  id: string;
  customer_id: string;
  customer_email: string;
  feedback_type: string;
  product_id?: string | null;
  conversation_id?: string | null;
  message: string;
  rating?: number | null;
  status: "PENDING" | "UNDER_REVIEW" | "RESOLVED" | "REJECTED";
  is_demo?: boolean;
  owner_resolution_note?: string | null;
  created_at: string;
  resolved_at?: string | null;
  reviewed_by?: string | null;
}

export interface PolicyData {
  is_ready: boolean;
  id?: string;
  title: string;
  version: string;
  content: string;
  sections: Record<string, { section_id: string; title: string; content: string; topic: string }>;
  created_at?: string;
  updated_at?: string;
}

export interface AuditLog {
  id: string;
  actor_id: string;
  actor_role: string;
  action: string;
  target_id: string;
  target_type: string;
  details?: any;
  timestamp: string;
}

export interface SystemStats {
  active_catalogue?: CatalogueVersion | null;
  active_policy?: any;
  total_valid_products: number;
  feedback: {
    total: number;
    pending: number;
    under_review: number;
    resolved: number;
    rejected: number;
  };
  last_evaluation?: {
    timestamp: string;
    total_questions: number;
    passed_count: number;
    citation_validity_rate: number;
  } | null;
  recent_audits: AuditLog[];
}

export interface QuestionEvaluationResult {
  question_id: string;
  query: string;
  expected_decision?: string | null;
  actual_decision: string;
  decision_match?: boolean | null;
  passed?: boolean;
  failure_reason?: string | null;
  citations: string[];
  citations_valid: boolean;
  has_unsupported_claims: boolean;
  latency_ms: number;
  token_cost?: number;
  notes?: string | null;
  evidence_preview?: string[];
}

export interface EvaluationReportResponse {
  report_id: string;
  timestamp: string;
  dataset_name: string;
  total_cases_available?: number;
  total_cases_executed?: number;
  total_cases_passed?: number;
  total_cases_failed?: number;
  total_cases_skipped?: number;
  total_questions_tested: number;
  successfully_evaluated: number;
  groundedness_score: number;
  answer_helpfulness_score: number;
  refusal_accuracy: number;
  clarification_accuracy: number;
  unsupported_claim_rate: number;
  citation_validity_rate: number;
  citation_coverage_rate?: number;
  avg_latency_ms: number;
  latency_p50_ms?: number;
  latency_p90_ms?: number;
  latency_p99_ms?: number;
  avg_token_cost?: number;
  total_token_cost?: number;
  data_readiness?: string | null;
  model_readiness?: string | null;
  compute_info: Record<string, any>;
  details: QuestionEvaluationResult[];
}
