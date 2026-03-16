import { Box, Paper, Typography, Chip } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import type { PolicyViolation } from '../services/api';

const SEV_COLORS: Record<string, string> = {
  critical: '#d32f2f', high: '#e65100', medium: '#ed6c02', low: '#2e7d32',
};

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function ViolationCard({ violation: v }: { violation: PolicyViolation }) {
  const color = SEV_COLORS[(v.severity ?? '').toLowerCase()] ?? '#757575';
  const tsS = v.timestampStart ?? v.timestamp_start ?? 0;
  const tsE = v.timestampEnd ?? v.timestamp_end ?? 0;
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningAmberIcon sx={{ color, fontSize: 20 }} />
          <Typography variant="subtitle2">{v.category}</Typography>
          {v.modality && <Chip label={v.modality} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />}
        </Box>
        <Chip label={v.severity?.toUpperCase()} size="small" sx={{ bgcolor: color, color: '#fff', fontWeight: 700 }} />
      </Box>
      <Chip label={`${fmt(tsS)} - ${fmt(tsE)}`} size="small" variant="outlined" sx={{ mb: 1, fontFamily: 'monospace' }} />
      {v.description && <Typography variant="body2" sx={{ mb: 0.5 }}>{v.description}</Typography>}
      {v.evidence && (
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          Evidence: {v.evidence}
        </Typography>
      )}
      {v.evidenceOriginal && (
        <Typography variant="caption" color="text.secondary" display="block">Original: {v.evidenceOriginal}</Typography>
      )}
      {v.transcription && (
        <Paper variant="outlined" sx={{ p: 1, mt: 1, bgcolor: '#f5f5f5', fontFamily: 'monospace', fontSize: '0.8rem' }}>
          {v.transcription}
        </Paper>
      )}
    </Paper>
  );
}
