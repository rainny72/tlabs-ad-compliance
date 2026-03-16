import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Box, Paper, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export default function LoginPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', gap: 16 }}>
      <Authenticator />
      <Paper variant="outlined" sx={{ p: 2, maxWidth: 380, bgcolor: '#f0f7ff', borderColor: '#90caf9' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <InfoOutlinedIcon fontSize="small" color="primary" />
          <Typography variant="subtitle2" color="primary">Demo Account</Typography>
        </Box>
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          ID: admin@adcompliance.com<br />
          PW: Admin1234!
        </Typography>
      </Paper>
    </div>
  );
}
