import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { ThemeProvider, CssBaseline, AppBar, Toolbar, Typography, Button, Box, Container, Chip, Paper } from '@mui/material';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import HistoryIcon from '@mui/icons-material/History';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import theme from './theme';
import AnalyzePage from './pages/AnalyzePage';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';

function NavLink({ to, label, icon }: { to: string; label: string; icon: React.ReactNode }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Button
      component={Link}
      to={to}
      startIcon={icon}
      sx={{
        color: active ? '#fff' : 'rgba(255,255,255,0.7)',
        borderBottom: active ? '2px solid #fff' : '2px solid transparent',
        borderRadius: 0,
        px: 2,
        '&:hover': { color: '#fff', backgroundColor: 'rgba(255,255,255,0.08)' },
      }}
    >
      {label}
    </Button>
  );
}

function DemoAccountBanner() {
  const { authStatus } = useAuthenticator((ctx) => [ctx.authStatus]);
  if (authStatus === 'authenticated') return null;
  return (
    <Paper variant="outlined" sx={{ mx: 'auto', mt: 2, p: 1.5, maxWidth: 380, bgcolor: '#f0f7ff', borderColor: '#90caf9' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
        <InfoOutlinedIcon sx={{ fontSize: 16 }} color="primary" />
        <Typography variant="caption" color="primary" fontWeight={600}>Demo Account</Typography>
      </Box>
      <Typography variant="caption" sx={{ fontFamily: 'monospace', lineHeight: 1.6 }}>
        ID: admin@adcompliance.com<br />
        PW: Admin1234!
      </Typography>
    </Paper>
  );
}

function AppContent() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
          <AppBar position="sticky" elevation={1}>
            <Toolbar>
              <Typography variant="h6" sx={{ mr: 4, fontWeight: 700 }}>
                Ad Compliance
              </Typography>
              <NavLink to="/analyze" label="Analyze" icon={<VideoLibraryIcon />} />
              <NavLink to="/history" label="History" icon={<HistoryIcon />} />
              <NavLink to="/settings" label="Settings" icon={<SettingsIcon />} />
              <Box sx={{ flexGrow: 1 }} />
              <Chip
                label={user?.signInDetails?.loginId}
                size="small"
                sx={{ color: 'rgba(255,255,255,0.9)', bgcolor: 'rgba(255,255,255,0.15)', mr: 1 }}
              />
              <Button color="inherit" onClick={signOut} startIcon={<LogoutIcon />} size="small">
                Sign out
              </Button>
            </Toolbar>
          </AppBar>
          <Container maxWidth="lg" sx={{ py: 3 }}>
            <Routes>
              <Route path="/" element={<Navigate to="/analyze" replace />} />
              <Route path="/analyze" element={<AnalyzePage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Container>
        </Box>
      )}
    </Authenticator>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Authenticator.Provider>
        <AppContent />
        <DemoAccountBanner />
      </Authenticator.Provider>
    </ThemeProvider>
  );
}

export default App;
