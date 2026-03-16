import { fetchAuthSession } from 'aws-amplify/auth';

const API_URL = import.meta.env.VITE_API_URL;

async function getAuthToken(): Promise<string> {
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  if (!token) {
    throw new Error('Authentication required');
  }
  return token;
}

async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: token,
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new ApiError(response.status, body.error || 'Request failed');
  }
  return response;
}

export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface UploadUrlResponse {
  uploadUrl: string;
  s3Key: string;
}

export interface AnalyzeRequest {
  s3Key: string;
  region: 'global' | 'north_america' | 'western_europe' | 'east_asia';
}

export interface AxisStatus {
  status: string;
  reasoning: string;
}

export interface CampaignRelevance {
  score: number;
  label: string;
  reasoning: string;
}

export interface PolicyViolation {
  category: string;
  severity: string;
  timestamp_start: number;
  timestamp_end: number;
  timestampStart?: number;
  timestampEnd?: number;
  evidence: string;
  description?: string;
  modality?: string;
  evidenceOriginal?: string;
  transcription?: string;
}

export interface AnalyzeResponse {
  reportId: string;
  decision: 'APPROVE' | 'REVIEW' | 'BLOCK';
  decisionReasoning: string;
  description: string;
  compliance: AxisStatus;
  product: AxisStatus;
  disclosure: AxisStatus;
  campaignRelevance: CampaignRelevance;
  policyViolations: PolicyViolation[];
  analyzedAt: string;
}

export interface JobResponse {
  jobId: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  result?: AnalyzeResponse;
  error?: string;
}

export interface ReportSummary {
  reportId: string;
  videoFile: string;
  decision: 'APPROVE' | 'REVIEW' | 'BLOCK';
  region: string;
  analyzedAt: string;
}

export interface ReportsListResponse {
  reports: ReportSummary[];
}

export async function getUploadUrl(filename: string, contentType: string): Promise<UploadUrlResponse> {
  const response = await authFetch('/upload-url', {
    method: 'POST',
    body: JSON.stringify({ filename, contentType }),
  });
  return response.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function snakeToCamel(obj: any): any {
  if (Array.isArray(obj)) return obj.map(snakeToCamel);
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [
        k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
        snakeToCamel(v),
      ]),
    );
  }
  return obj;
}

export async function submitAnalysis(request: AnalyzeRequest): Promise<{ jobId: string }> {
  const response = await authFetch('/analyze', {
    method: 'POST',
    body: JSON.stringify(request),
  });
  return response.json();
}

export async function getJobStatus(jobId: string): Promise<JobResponse> {
  const response = await authFetch(`/analyze/${jobId}`);
  const raw = await response.json();
  return snakeToCamel(raw) as JobResponse;
}

export async function analyzeVideo(
  request: AnalyzeRequest,
  onStatusChange?: (status: string) => void,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const { jobId } = await submitAnalysis(request);

  const POLL_INTERVAL = 5000; // 5 seconds
  const MAX_POLLS = 60; // 5 minutes max

  for (let i = 0; i < MAX_POLLS; i++) {
    if (signal?.aborted) {
      throw new ApiError(0, 'Analysis cancelled');
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL));

    const job = await getJobStatus(jobId);
    onStatusChange?.(job.status);

    if (job.status === 'COMPLETED') {
      if (!job.result) throw new ApiError(500, 'No result in completed job');
      return job.result;
    }

    if (job.status === 'FAILED') {
      throw new ApiError(500, job.error || 'Analysis failed');
    }
  }

  throw new ApiError(408, 'Analysis timed out. Please try again later.');
}

export async function listReports(): Promise<ReportsListResponse> {
  const response = await authFetch('/reports');
  const raw = await response.json();
  return snakeToCamel(raw) as ReportsListResponse;
}

export async function getReport(reportId: string): Promise<AnalyzeResponse> {
  const response = await authFetch(`/reports/${reportId}`);
  const raw = await response.json();
  return snakeToCamel(raw) as AnalyzeResponse;
}

export interface UserSettings {
  backend: 'bedrock' | 'twelvelabs';
  twelvelabsApiKey: string;
  bedrockRegion: string;
}

export async function getSettings(): Promise<UserSettings> {
  const response = await authFetch('/settings');
  return response.json();
}

export async function saveSettings(settings: Partial<UserSettings>): Promise<void> {
  await authFetch('/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}
