export type Role = "admin" | "steward" | "editor" | "viewer";

export interface User {
  id: number;
  username: string;
  role: Role;
}

export interface Citation {
  id: number;
  cited_text: string;
  page_number: number | null;
  verified: boolean;
}

export interface LineItem {
  id: number;
  field_name: string;
  raw_label: string | null;
  value: number | null;
  unit: string | null;
  period: string | null;
  confidence: "high" | "medium" | "low" | "manual";
  is_outlier: boolean;
  version: number;
  last_updated: string;
  citations: Citation[];
}

export interface StatementListItem {
  id: number;
  filename: string;
  company_name: string | null;
  statement_type: string | null;
  fiscal_period: string | null;
  classification: "Public" | "Internal" | "Confidential" | "Restricted";
  status: "processing" | "processed" | "quarantined" | "error";
  quality_score: number | null;
  uploaded_at: string;
  last_updated: string;
}

export interface StatementDetail extends StatementListItem {
  currency: string | null;
  ai_notes: string | null;
  error_detail: string | null;
  completeness_score: number | null;
  validity_score: number | null;
  consistency_score: number | null;
  uniqueness_score: number | null;
  citation_coverage_score: number | null;
  version: number;
  owner_id: number | null;
  steward_id: number | null;
  uploaded_by_id: number | null;
  line_items: LineItem[];
}

export interface QuarantineItem {
  id: number;
  statement_id: number;
  line_item_id: number | null;
  reason_code: string;
  detail: string;
  status: "pending" | "reviewed" | "resolved";
  created_at: string;
  reviewed_by_id: number | null;
  reviewed_at: string | null;
  resolution_note: string | null;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: number | null;
  action: string;
  username: string | null;
  timestamp: string;
  detail: string | null;
  old_value: string | null;
  new_value: string | null;
}

export interface DataDictionaryEntry {
  field_name: string;
  type: string;
  description: string;
  source: string;
  owner: string;
}

export interface DashboardMetrics {
  total_statements: number;
  avg_quality_score: number | null;
  avg_completeness_pct: number | null;
  quarantine_pending_count: number;
  stale_record_count: number;
  last_audit_at: string | null;
  quality_trend: { label: string; score: number; uploaded_at: string }[];
  recent_statements: StatementListItem[];
}
