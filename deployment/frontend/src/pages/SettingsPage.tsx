import { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Button, TextField, Alert,
  CircularProgress, Radio, RadioGroup, FormControlLabel, FormControl,
  FormLabel, Divider, Chip, Stack, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import SaveIcon from '@mui/icons-material/Save';
import CloudIcon from '@mui/icons-material/Cloud';
import KeyIcon from '@mui/icons-material/Key';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import { getSettings, saveSettings } from '../services/api';

export default function SettingsPage() {
  const [backend, setBackend] = useState<'bedrock' | 'twelvelabs'>('bedrock');
  const [twelvelabsApiKey, setTwelvelabsApiKey] = useState('');
  const [bedrockRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    try {
      const s = await getSettings();
      setBackend(s.backend || 'bedrock');
      setTwelvelabsApiKey(s.twelvelabsApiKey || '');
    } catch {
      // First time - no settings yet, use defaults
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (backend === 'twelvelabs' && !twelvelabsApiKey.trim()) {
        setError('TwelveLabs API Key is required when using TwelveLabs backend');
        setSaving(false);
        return;
      }
      await saveSettings({ backend, twelvelabsApiKey, bedrockRegion });
      setSuccess('Settings saved successfully');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <CircularProgress size={48} />
        <Typography sx={{ mt: 2 }} color="text.secondary">Loading settings...</Typography>
      </Box>
    );
  }

  const keyPreview = twelvelabsApiKey ? twelvelabsApiKey.slice(0, 8) + '...' : '';

  return (
    <Box>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <SettingsIcon color="primary" /> Settings
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Configure default API backend and credentials
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      {/* Backend Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <FormControl component="fieldset">
            <FormLabel component="legend" sx={{ fontWeight: 600, mb: 1 }}>
              Backend
            </FormLabel>
            <RadioGroup
              row
              value={backend}
              onChange={(e) => { setBackend(e.target.value as 'bedrock' | 'twelvelabs'); setSuccess(null); }}
            >
              <FormControlLabel
                value="bedrock"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <CloudIcon fontSize="small" color="action" />
                    Amazon Bedrock (Pegasus 1.2)
                  </Box>
                }
              />
              <FormControlLabel
                value="twelvelabs"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <KeyIcon fontSize="small" color="action" />
                    TwelveLabs API (Direct)
                  </Box>
                }
              />
            </RadioGroup>
          </FormControl>
        </CardContent>
      </Card>

      <Divider sx={{ mb: 3 }} />

      {/* Backend-specific settings */}
      {backend === 'bedrock' ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
              Amazon Bedrock Configuration
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, bgcolor: '#f5f5f5' }}>
              <Stack spacing={1}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" color="text.secondary">Region:</Typography>
                  <Chip label="us-east-1" size="small" variant="outlined" />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Pegasus 1.2 is currently available in us-east-1 only.
                  Lambda uses IAM Role for authentication (no credentials needed).
                </Typography>
              </Stack>
            </Paper>
            <Alert severity="success" sx={{ mt: 2 }} icon={false}>
              Bedrock is configured via IAM Role - no additional credentials required
            </Alert>
          </CardContent>
        </Card>
      ) : (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
              TwelveLabs API Credentials
            </Typography>
            <TextField
              fullWidth
              label="TwelveLabs API Key"
              type="password"
              value={twelvelabsApiKey}
              onChange={(e) => { setTwelvelabsApiKey(e.target.value); setSuccess(null); }}
              placeholder="Enter your TwelveLabs API key"
              sx={{ mb: 2 }}
            />
            {twelvelabsApiKey ? (
              <Alert severity="success" icon={false}>
                API key set ({keyPreview})
              </Alert>
            ) : (
              <Alert severity="info" icon={false}>
                Enter TwelveLabs API key to use direct API
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Backend Comparison */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <CompareArrowsIcon fontSize="small" color="primary" /> Backend Comparison
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'grey.50' }}>
                  <TableCell sx={{ fontWeight: 600 }}></TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="center">Amazon Bedrock</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="center">TwelveLabs API</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[
                  ['Model', 'Pegasus 1.2 (via Bedrock)', 'Pegasus 1.2 (Direct REST)'],
                  ['API Version', 'Bedrock InvokeModel', 'TwelveLabs v1.3'],
                  ['Video Upload', 'Base64 inline (max ~25 MB)', 'Multipart upload (max 2 GB)'],
                  ['Processing', 'Single API call (no indexing)', 'Upload → Index → Analyze'],
                  ['Authentication', 'IAM Role (no key needed)', 'API Key required'],
                  ['Region', 'us-east-1 only', 'Global (TwelveLabs cloud)'],
                  ['Latency', '~30s–2 min', '~1–5 min (indexing included)'],
                  ['Cost', 'AWS Bedrock pricing', 'TwelveLabs credit-based'],
                ].map(([label, bedrock, tl]) => (
                  <TableRow key={label} sx={{ '&:last-child td': { borderBottom: 0 } }}>
                    <TableCell sx={{ fontWeight: 500, color: 'text.secondary', whiteSpace: 'nowrap' }}>{label}</TableCell>
                    <TableCell align="center">{bedrock}</TableCell>
                    <TableCell align="center">{tl}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Both backends use the same Pegasus 1.2 model. Bedrock is simpler (no indexing step), while TwelveLabs supports larger files and provides its own video management.
          </Typography>
        </CardContent>
      </Card>

      {/* Save Button */}
      <Button
        variant="contained"
        size="large"
        startIcon={saving ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? 'Saving...' : 'Save Settings'}
      </Button>
    </Box>
  );
}
