export type JobStatus =
  | "queued"
  | "processing"
  | "ocr_running"
  | "face_verification"
  | "matching"
  | "completed"
  | "failed"
  | "cancelled";

export type VerificationDecision = "verified" | "review_required" | "rejected" | "failed";

export interface DocumentMeta {
  document_id: string;
  role: "primary" | "supporting";
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface JobDetail {
  job_id: string;
  status: JobStatus;
  status_reason?: string;
  external_reference?: string;
  queued_at?: string;
  completed_at?: string;
  documents: DocumentMeta[];
}

export interface FieldScores {
  name_match_score?: number;
  dob_match_score?: number;
  address_match_score?: number;
  id_number_match_score?: number;
  face_match_score?: number;
  overall_score?: number;
  identity_verification?: {
    name_match_pct?: number;
    dob_match_pct?: number;
    dob_match?: boolean;
    gender_match?: boolean;
  };
  address_verification?: {
    house_score?: number;
    street_score?: number;
    city_score?: number;
    state_score?: number;
    postal_score?: number;
  };
  document_verification?: {
    pan_match?: boolean;
    aadhaar_match?: boolean;
    passport_match?: boolean;
    dl_match?: boolean;
    voter_match?: boolean;
  };
  face_verification?: {
    distance?: number;
    similarity?: number;
    verdict?: string;
  };
  final_verification?: {
    score?: number;
    verdict?: string;
  };
}

export interface VerificationReport {
  decision: VerificationDecision;
  overall_score: number;
  field_scores: FieldScores;
  report: {
    extracted_entities?: {
      primary?: Record<string, any>;
      supporting?: Record<string, any>;
    };
    normalized_entities?: {
      primary?: Record<string, any>;
      supporting?: Record<string, any>;
    };
    face_verification?: Record<string, any>;
    verified_at?: string;
  };
}

export interface AuditLogItem {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface SSEEventData {
  event_type: string;
  status?: string;
  decision?: string;
  overall_score?: number;
  document_id?: string;
  filename?: string;
  role?: string;
  error?: string;
}
