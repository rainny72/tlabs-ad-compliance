import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Button, Select, MenuItem, FormControl, InputLabel,
  CircularProgress, Alert, Chip, Divider, Paper, Grid, LinearProgress, Stack,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DownloadIcon from '@mui/icons-material/Download';
import ShieldIcon from '@mui/icons-material/Shield';
import InventoryIcon from '@mui/icons-material/Inventory';
import AnnouncementIcon from '@mui/icons-material/Announcement';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import VideoUploader from '../components/VideoUploader';
import { analyzeVideo, getSettings, ApiError } from '../services/api';
import type { AnalyzeResponse, PolicyViolation } from '../services/api';

type Region = 'global' | 'north_america' | 'western_europe' | 'east_asia';

const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: 'global', label: 'Global' },
  { value: 'north_america', label: 'North America (FTC/FDA)' },
  { value: 'western_europe', label: 'Western Europe (ASA/EU)' },
  { value: 'east_asia', label: 'East Asia (KR/JP/CN)' },
];

const DECISION_STYLES: Record<string, { bg: string; color: string }> = {
  APPROVE: { bg: '#2e7d32', color: '#fff' },
  REVIEW: { bg: '#ed6c02', color: '#fff' },
  BLOCK: { bg: '#d32f2f', color: '#fff' },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#d32f2f', high: '#e65100', medium: '#ed6c02', low: '#2e7d32',
};

const STATUS_COLORS: Record<string, string> = {
  PASS: '#2e7d32', ON_BRIEF: '#2e7d32', PRESENT: '#2e7d32',
  REVIEW: '#ed6c02', BORDERLINE: '#ed6c02', NOT_VISIBLE: '#ed6c02',
  BLOCK: '#d32f2f', MISSING: '#ed6c02', OFF_BRIEF: '#d32f2f',
};

interface CategoryViolation {
  category: string;
  severity: string;
  violations: PolicyViolation[];
}

function flattenViolations(pv: (CategoryViolation | PolicyViolation)[]): PolicyViolation[] {
  if (!Array.isArray(pv)) return [];
  const flat: PolicyViolation[] = [];
  for (const item of pv) {
    if ('violations' in item && Array.isArray(item.violations)) {
      for (const v of item.violations) {
        flat.push({ ...v, category: item.category, severity: (v as PolicyViolation).severity || item.severity });
      }
    } else {
      flat.push(item as PolicyViolation);
    }
  }
  return flat;
}

function downloadJson(data: AnalyzeResponse, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function AxisCard({ title, icon, status, reasoning, extra }: {
  title: string; icon: React.ReactNode; status: string; reasoning: string; extra?: React.ReactNode;
}) {
  const color = STATUS_COLORS[status] ?? '#757575';
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {icon}
          <Typography variant="subtitle2" color="text.secondary">{title}</Typography>
        </Box>
        <Chip label={status} size="small" sx={{ bgcolor: color, color: '#fff', fontWeight: 700, mb: 1 }} />
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.5 }}>
          {reasoning}
        </Typography>
        {extra}
      </CardContent>
    </Card>
  );
}

function ViolationThumbnail({ videoUrl, timestamp }: { videoUrl: string; timestamp: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [captured, setCaptured] = useState(false);

  useEffect(() => {
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.muted = true;
    video.preload = 'auto';
    video.src = videoUrl;

    function onSeeked() {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0);
        setCaptured(true);
      }
      video.removeEventListener('seeked', onSeeked);
      video.src = '';
    }

    video.addEventListener('loadeddata', () => {
      video.currentTime = Math.min(timestamp, video.duration - 0.1);
    });
    video.addEventListener('seeked', onSeeked);
    video.load();

    return () => { video.src = ''; };
  }, [videoUrl, timestamp]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%', borderRadius: 6, backgroundColor: '#000',
        display: captured ? 'block' : 'none',
      }}
    />
  );
}

function ViolationClipPlayer({ videoUrl, start, end }: { videoUrl: string; start: number; end: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    el.currentTime = Math.max(0, start);

    function onTimeUpdate() {
      if (el && el.currentTime >= end) {
        el.pause();
        el.currentTime = Math.max(0, start);
      }
    }
    el.addEventListener('timeupdate', onTimeUpdate);
    return () => el.removeEventListener('timeupdate', onTimeUpdate);
  }, [start, end]);

  return (
    <video
      ref={videoRef}
      src={videoUrl}
      controls
      style={{ width: '100%', borderRadius: 6, maxHeight: 180, backgroundColor: '#000' }}
    />
  );
}

function ViolationDetailCard({ v, videoUrl }: { v: PolicyViolation; videoUrl: string | null }) {
  const sevColor = SEVERITY_COLORS[(v.severity ?? '').toLowerCase()] ?? '#757575';
  const tsStart = v.timestampStart ?? v.timestamp_start ?? 0;
  const tsEnd = v.timestampEnd ?? v.timestamp_end ?? 0;
  const midTime = (tsStart + tsEnd) / 2;
  const hasVideo = !!videoUrl;

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningAmberIcon sx={{ color: sevColor, fontSize: 20 }} />
          <Typography variant="subtitle2">{v.category}</Typography>
          {v.modality && <Chip label={v.modality} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />}
        </Box>
        <Chip label={v.severity?.toUpperCase()} size="small" sx={{ bgcolor: sevColor, color: '#fff', fontWeight: 700 }} />
      </Box>
      <Box sx={{ display: 'flex', gap: 2, flexDirection: hasVideo ? 'row' : 'column' }}>
        {hasVideo && (
          <Box sx={{ flex: '0 0 200px', maxWidth: 200 }}>
            <ViolationThumbnail videoUrl={videoUrl} timestamp={midTime} />
            <ViolationClipPlayer videoUrl={videoUrl} start={tsStart} end={tsEnd} />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block', textAlign: 'center' }}>
              @ {formatTime(tsStart)} - {formatTime(tsEnd)}
            </Typography>
          </Box>
        )}
        <Box sx={{ flex: 1 }}>
          {!hasVideo && (
            <Chip
              label={`${formatTime(tsStart)} - ${formatTime(tsEnd)}`}
              size="small" variant="outlined" sx={{ mb: 1, fontFamily: 'monospace' }}
            />
          )}
          {v.description && (
            <Typography variant="body2" sx={{ mb: 0.5 }}>{v.description}</Typography>
          )}
          {v.evidence && (
            <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mb: 0.5 }}>
              Evidence: {v.evidence}
            </Typography>
          )}
          {v.evidenceOriginal && (
            <Typography variant="caption" color="text.secondary" display="block">
              Original: {v.evidenceOriginal}
            </Typography>
          )}
          {v.transcription && (
            <Paper variant="outlined" sx={{ p: 1, mt: 1, bgcolor: '#f5f5f5', fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {v.transcription}
            </Paper>
          )}
        </Box>
      </Box>
    </Paper>
  );
}

export default function AnalyzePage() {
  const [s3Key, setS3Key] = useState<string | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [region, setRegion] = useState<Region>('global');
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backend, setBackend] = useState<string>('bedrock');
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const videoUrl = useMemo(() => videoFile ? URL.createObjectURL(videoFile) : null, [videoFile]);

  useEffect(() => {
    getSettings().then((s) => setBackend(s.backend || 'bedrock')).catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleUploadComplete = useCallback((key: string, filename: string) => {
    setS3Key(key);
    setUploadedFilename(filename);
    setResult(null);
    setError(null);
  }, []);

  const handleFileSelected = useCallback((file: File | null) => {
    setVideoFile(file);
  }, []);

  async function handleAnalyze() {
    if (!s3Key) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    setJobStatus(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await analyzeVideo(
        { s3Key, region },
        (status) => setJobStatus(status),
        controller.signal,
      );
      setResult(response);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 0) return; // cancelled, ignore
        setError(err.statusCode === 503 ? 'Service temporarily unavailable. Please try again later.' : err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setAnalyzing(false);
      setJobStatus(null);
      abortControllerRef.current = null;
    }
  }

  const violations = result ? flattenViolations(result.policyViolations) : [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CloudUploadIcon color="primary" /> Video Compliance Analysis
      </Typography>

      {/* Upload + Region row */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: videoUrl ? 6 : 12 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                1. Upload Video
              </Typography>
              <VideoUploader onUploadComplete={handleUploadComplete} onFileSelected={handleFileSelected} />
              {s3Key && (
                <Alert severity="success" sx={{ mt: 1 }}>Uploaded: {uploadedFilename}</Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
        {videoUrl && (
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                  Video Preview
                </Typography>
                <video
                  src={videoUrl}
                  controls
                  style={{ width: '100%', borderRadius: 8, maxHeight: 300, backgroundColor: '#000' }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {uploadedFilename || videoFile?.name}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Region + Analyze */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            2. Select Region & Analyze
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 240 }}>
              <InputLabel id="region-label">Target Region</InputLabel>
              <Select
                labelId="region-label"
                value={region}
                label="Target Region"
                onChange={(e) => setRegion(e.target.value as Region)}
                disabled={analyzing}
              >
                {REGION_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              size="large"
              onClick={handleAnalyze}
              disabled={!s3Key || analyzing}
              startIcon={analyzing ? <CircularProgress size={20} color="inherit" /> : undefined}
            >
              {analyzing ? 'Analyzing...' : 'Run Analysis'}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {/* Loading */}
      {analyzing && (
        <Card sx={{ mb: 3 }}>
          <CardContent sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress size={48} sx={{ mb: 2 }} />
            <Typography variant="body1" color="text.secondary">
              {jobStatus === 'PROCESSING'
                ? (backend === 'twelvelabs'
                  ? 'Analyzing video with TwelveLabs API... This may take 2-5 minutes.'
                  : 'Analyzing video with Amazon Bedrock... This may take 1-3 minutes.')
                : jobStatus === 'PENDING'
                  ? 'Analysis queued, waiting to start...'
                  : 'Submitting analysis request...'}
            </Typography>
            <LinearProgress sx={{ mt: 2, mx: 'auto', maxWidth: 400 }} />
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {/* Results */}
      {result && (
        <>
          {/* Decision Banner */}
          <Paper
            sx={{
              p: 2.5, mb: 3, borderRadius: 2,
              bgcolor: DECISION_STYLES[result.decision]?.bg ?? '#757575',
              color: '#fff',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box>
                <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Campaign Decision: {result.decision}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.92 }}>
                  {result.decisionReasoning}
                </Typography>
              </Box>
              <Button
                variant="outlined"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={() => downloadJson(result, `report-${result.reportId}.json`)}
                sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.5)', flexShrink: 0, ml: 2,
                  '&:hover': { borderColor: '#fff', bgcolor: 'rgba(255,255,255,0.1)' } }}
              >
                JSON
              </Button>
            </Box>
          </Paper>

          {/* Description */}
          {result.description && (
            <Alert severity="info" sx={{ mb: 3 }} icon={false}>
              <Typography variant="subtitle2" gutterBottom>Video Description</Typography>
              <Typography variant="body2">{result.description}</Typography>
            </Alert>
          )}

          {/* 3-Axis Cards */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, md: 4 }}>
              <AxisCard
                title="Compliance"
                icon={<ShieldIcon sx={{ color: STATUS_COLORS[result.compliance?.status] ?? '#757575' }} />}
                status={result.compliance?.status ?? 'N/A'}
                reasoning={result.compliance?.reasoning ?? ''}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <AxisCard
                title="Product"
                icon={<InventoryIcon sx={{ color: STATUS_COLORS[result.product?.status] ?? '#757575' }} />}
                status={result.product?.status ?? 'N/A'}
                reasoning={result.product?.reasoning ?? ''}
                extra={result.campaignRelevance && (
                  <Box sx={{ mt: 1.5, p: 1.5, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="caption" color="text.secondary">Campaign Relevance</Typography>
                    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        {Number(result.campaignRelevance.score ?? 0).toFixed(2)}
                      </Typography>
                      <Chip label={result.campaignRelevance.label} size="small" variant="outlined" />
                    </Box>
                    {result.campaignRelevance.reasoning && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                        {result.campaignRelevance.reasoning}
                      </Typography>
                    )}
                  </Box>
                )}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <AxisCard
                title="Disclosure"
                icon={<AnnouncementIcon sx={{ color: STATUS_COLORS[result.disclosure?.status] ?? '#757575' }} />}
                status={result.disclosure?.status ?? 'N/A'}
                reasoning={result.disclosure?.reasoning ?? ''}
              />
            </Grid>
          </Grid>

          {/* Policy Violations */}
          {violations.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <WarningAmberIcon color="warning" />
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    Policy Violations ({violations.length})
                  </Typography>
                </Box>
                {violations.map((v, i) => (
                  <ViolationDetailCard key={i} v={v} videoUrl={videoUrl} />
                ))}
              </CardContent>
            </Card>
          )}

          {/* Footer */}
          <Divider sx={{ mb: 2 }} />
          <Typography variant="caption" color="text.secondary">
            Analyzed at: {result.analyzedAt} | Report ID: {result.reportId}
          </Typography>
        </>
      )}
    </Box>
  );
}
