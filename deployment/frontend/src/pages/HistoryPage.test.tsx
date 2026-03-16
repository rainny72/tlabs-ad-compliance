import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import HistoryPage from './HistoryPage';

vi.mock('../services/api', () => ({
  listReports: vi.fn(),
  getReport: vi.fn(),
  ApiError: class ApiError extends Error {
    statusCode: number;
    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
      this.name = 'ApiError';
    }
  },
}));

vi.mock('../components/ComplianceResult', () => ({
  default: ({ result }: { result: { decision: string } }) => (
    <div data-testid="compliance-result">Decision: {result.decision}</div>
  ),
}));

vi.mock('../components/ViolationCard', () => ({
  default: ({ violation }: { violation: { category: string } }) => (
    <div data-testid="violation-card">{violation.category}</div>
  ),
}));

import { listReports, getReport } from '../services/api';
const mockListReports = vi.mocked(listReports);
const mockGetReport = vi.mocked(getReport);

const MOCK_REPORTS = [
  { reportId: 'r1', videoFile: 'ad1.mp4', decision: 'APPROVE' as const, region: 'global', analyzedAt: '2024-06-01T10:00:00Z' },
  { reportId: 'r2', videoFile: 'ad2.mp4', decision: 'REVIEW' as const, region: 'north_america', analyzedAt: '2024-06-02T10:00:00Z' },
  { reportId: 'r3', videoFile: 'ad3.mp4', decision: 'BLOCK' as const, region: 'east_asia', analyzedAt: '2024-06-03T10:00:00Z' },
  { reportId: 'r4', videoFile: 'ad4.mp4', decision: 'APPROVE' as const, region: 'western_europe', analyzedAt: '2024-06-04T10:00:00Z' },
];

const MOCK_DETAIL = {
  reportId: 'r1',
  decision: 'APPROVE' as const,
  decisionReasoning: 'Content is compliant',
  description: 'Test video',
  compliance: { status: 'PASS', reasoning: 'No violations' },
  product: { status: 'ON_BRIEF', reasoning: 'Product visible' },
  disclosure: { status: 'PRESENT', reasoning: 'Disclosure found' },
  campaignRelevance: { score: 0.9, label: 'ON_BRIEF', reasoning: 'Relevant' },
  policyViolations: [],
  analyzedAt: '2024-06-01T10:00:00Z',
};

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockListReports.mockImplementation(() => new Promise(() => {}));
    render(<HistoryPage />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading reports...');
  });

  it('displays report list after fetch', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });
    expect(screen.getByText('ad2.mp4')).toBeInTheDocument();
    expect(screen.getByText('ad3.mp4')).toBeInTheDocument();
    expect(screen.getByText('ad4.mp4')).toBeInTheDocument();
  });

  it('shows summary metrics', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByTestId('metric-total')).toHaveTextContent('4');
    });
    expect(screen.getByTestId('metric-approve')).toHaveTextContent('2');
    expect(screen.getByTestId('metric-review')).toHaveTextContent('1');
    expect(screen.getByTestId('metric-block')).toHaveTextContent('1');
  });

  it('filters by decision type', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('filter-approve'));
    expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    expect(screen.getByText('ad4.mp4')).toBeInTheDocument();
    expect(screen.queryByText('ad2.mp4')).not.toBeInTheDocument();
    expect(screen.queryByText('ad3.mp4')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('filter-block'));
    expect(screen.getByText('ad3.mp4')).toBeInTheDocument();
    expect(screen.queryByText('ad1.mp4')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('filter-all'));
    expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    expect(screen.getByText('ad2.mp4')).toBeInTheDocument();
    expect(screen.getByText('ad3.mp4')).toBeInTheDocument();
  });

  it('navigates to detail view on click', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    mockGetReport.mockResolvedValue(MOCK_DETAIL);
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('report-row-r1'));

    await waitFor(() => {
      expect(screen.getByTestId('compliance-result')).toBeInTheDocument();
    });
    expect(mockGetReport).toHaveBeenCalledWith('r1');
  });

  it('shows back button in detail view', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    mockGetReport.mockResolvedValue(MOCK_DETAIL);
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('report-row-r1'));

    await waitFor(() => {
      expect(screen.getByTestId('back-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('back-button'));

    await waitFor(() => {
      expect(screen.getByTestId('history-page')).toBeInTheDocument();
    });
  });

  it('handles API errors on list fetch', async () => {
    mockListReports.mockRejectedValue(new Error('Network error'));
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network error');
    });
  });

  it('handles API errors on detail fetch', async () => {
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    mockGetReport.mockRejectedValue(new Error('Report not found'));
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('report-row-r1'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Report not found');
    });
  });

  it('handles empty report list', async () => {
    mockListReports.mockResolvedValue({ reports: [] });
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByText(/no reports yet/i)).toBeInTheDocument();
  });

  it('shows violations in detail view when present', async () => {
    const detailWithViolations = {
      ...MOCK_DETAIL,
      decision: 'BLOCK' as const,
      policyViolations: [
        { category: 'hate_speech', severity: 'high', timestamp_start: 5, timestamp_end: 15, evidence: 'Offensive content' },
      ],
    };
    mockListReports.mockResolvedValue({ reports: MOCK_REPORTS });
    mockGetReport.mockResolvedValue(detailWithViolations);
    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ad1.mp4')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('report-row-r1'));

    await waitFor(() => {
      expect(screen.getByTestId('violation-card')).toBeInTheDocument();
    });
    expect(screen.getByText('hate_speech')).toBeInTheDocument();
  });
});
