import { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Button, Chip, CircularProgress, Alert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Stack, Grid,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import { listReports, getReport } from '../services/api';
import type { ReportSummary, AnalyzeResponse, PolicyViolation } from '../services/api';
import ComplianceResult from '../components/ComplianceResult';
import ViolationCard from '../components/ViolationCard';

type DecisionFilter = 'ALL' | 'APPROVE' | 'REVIEW' | 'BLOCK';

interface CategoryViolation { category: string; severity: string; violations: PolicyViolation[]; }

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
  return flat.filter((v) => (v.severity ?? '').toUpperCase() !== 'NONE');
}

const DECISION_COLORS: Record<string, string> = {
  APPROVE: '#2e7d32', REVIEW: '#ed6c02', BLOCK: '#d32f2f',
};

export default function HistoryPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [filter, setFilter] = useState<DecisionFilter>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<AnalyzeResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => { loadReports(); }, []);

  async function loadReports() {
    setLoading(true); setError(null);
    try {
      const data = await listReports();
      setReports(data.reports ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports');
    } finally { setLoading(false); }
  }

  async function handleReportClick(reportId: string) {
    setDetailLoading(true); setDetailError(null);
    try {
      const detail = await getReport(reportId);
      setSelectedReport(detail);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Failed to load report');
    } finally { setDetailLoading(false); }
  }

  function handleBack() { setSelectedReport(null); setDetailError(null); }

  const filtered = filter === 'ALL' ? reports : reports.filter((r) => r.decision === filter);
  const counts = {
    total: reports.length,
    approve: reports.filter((r) => r.decision === 'APPROVE').length,
    review: reports.filter((r) => r.decision === 'REVIEW').length,
    block: reports.filter((r) => r.decision === 'BLOCK').length,
  };

  if (detailLoading) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <CircularProgress size={48} />
        <Typography sx={{ mt: 2 }} color="text.secondary">Loading report details...</Typography>
      </Box>
    );
  }

  if (selectedReport) {
    const violations = flattenViolations(selectedReport.policyViolations ?? []);
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} sx={{ mb: 2 }}>Back to list</Button>
        <ComplianceResult result={selectedReport} />
        {violations.length > 0 && (
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                Policy Violations ({violations.length})
              </Typography>
              {violations.map((v, i) => (
                <ViolationCard key={i} violation={v} />
              ))}
            </CardContent>
          </Card>
        )}
      </Box>
    );
  }

  if (detailError) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} sx={{ mb: 2 }}>Back to list</Button>
        <Alert severity="error">{detailError}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <HistoryIcon color="primary" /> Analysis History
      </Typography>

      {/* Summary Metrics */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: 'Total', count: counts.total, color: '#424242' },
          { label: 'APPROVE', count: counts.approve, color: DECISION_COLORS.APPROVE },
          { label: 'REVIEW', count: counts.review, color: DECISION_COLORS.REVIEW },
          { label: 'BLOCK', count: counts.block, color: DECISION_COLORS.BLOCK },
        ].map((m) => (
          <Grid size={{ xs: 6, sm: 3 }} key={m.label}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                <Typography variant="h4" sx={{ fontWeight: 700, color: m.color }}>{m.count}</Typography>
                <Typography variant="caption" color="text.secondary">{m.label}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Filter */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        {(['ALL', 'APPROVE', 'REVIEW', 'BLOCK'] as DecisionFilter[]).map((f) => (
          <Button
            key={f} size="small"
            variant={filter === f ? 'contained' : 'outlined'}
            onClick={() => setFilter(f)}
          >
            {f}
          </Button>
        ))}
      </Stack>

      {loading && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {!loading && !error && reports.length === 0 && (
        <Alert severity="info">No reports yet. Analyze a video to see results here.</Alert>
      )}

      {!loading && !error && filtered.length > 0 && (
        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: '#fafafa' }}>
                <TableCell sx={{ fontWeight: 600 }}>Video</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Decision</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Region</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Analyzed</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map((r) => (
                <TableRow
                  key={r.reportId}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => handleReportClick(r.reportId)}
                >
                  <TableCell>{r.videoFile}</TableCell>
                  <TableCell>
                    <Chip
                      label={r.decision} size="small"
                      sx={{ bgcolor: DECISION_COLORS[r.decision] ?? '#757575', color: '#fff', fontWeight: 700 }}
                    />
                  </TableCell>
                  <TableCell>{r.region}</TableCell>
                  <TableCell>{new Date(r.analyzedAt).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
