import { Box, Paper, Typography, Chip, Grid, Card, CardContent, Alert } from '@mui/material';
import ShieldIcon from '@mui/icons-material/Shield';
import InventoryIcon from '@mui/icons-material/Inventory';
import AnnouncementIcon from '@mui/icons-material/Announcement';
import type { AnalyzeResponse, PolicyViolation } from '../services/api';

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

export interface ComplianceResultProps { result: AnalyzeResponse; }

const DECISION_BG: Record<string, string> = { APPROVE: '#2e7d32', REVIEW: '#ed6c02', BLOCK: '#d32f2f' };
const STATUS_COLORS: Record<string, string> = {
  PASS: '#2e7d32', ON_BRIEF: '#2e7d32', PRESENT: '#2e7d32',
  REVIEW: '#ed6c02', BORDERLINE: '#ed6c02', NOT_VISIBLE: '#ed6c02',
  BLOCK: '#d32f2f', MISSING: '#ed6c02', OFF_BRIEF: '#d32f2f',
};

export default function ComplianceResult({ result }: ComplianceResultProps) {
  return (
    <Box data-testid="compliance-result">
      <Paper sx={{ p: 2.5, mb: 2, bgcolor: DECISION_BG[result.decision] ?? '#757575', color: '#fff', borderRadius: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>Decision: {result.decision}</Typography>
        {result.decisionReasoning && (
          <Typography variant="body2" sx={{ mt: 0.5, opacity: 0.92 }}>{result.decisionReasoning}</Typography>
        )}
      </Paper>
      {result.description && (
        <Alert severity="info" sx={{ mb: 2 }} icon={false}>
          <Typography variant="body2">{result.description}</Typography>
        </Alert>
      )}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {[
          { title: 'Compliance', icon: <ShieldIcon />, data: result.compliance },
          { title: 'Product', icon: <InventoryIcon />, data: result.product },
          { title: 'Disclosure', icon: <AnnouncementIcon />, data: result.disclosure },
        ].map(({ title, icon, data }) => (
          <Grid size={{ xs: 12, md: 4 }} key={title}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  {icon}
                  <Typography variant="subtitle2" color="text.secondary">{title}</Typography>
                </Box>
                <Chip
                  label={data?.status ?? 'N/A'} size="small"
                  sx={{ bgcolor: STATUS_COLORS[data?.status] ?? '#757575', color: '#fff', fontWeight: 700, mb: 1 }}
                />
                <Typography variant="body2" color="text.secondary">{data?.reasoning}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      {result.campaignRelevance && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">Campaign Relevance</Typography>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mt: 0.5 }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>{Number(result.campaignRelevance.score ?? 0).toFixed(2)}</Typography>
            <Chip label={result.campaignRelevance.label} size="small" variant="outlined" />
          </Box>
          {result.campaignRelevance.reasoning && (
            <Typography variant="caption" color="text.secondary">{result.campaignRelevance.reasoning}</Typography>
          )}
        </Paper>
      )}
      <Typography variant="caption" color="text.secondary">
        Policy Violations: {flattenViolations(result.policyViolations ?? []).length}
      </Typography>
    </Box>
  );
}
