import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AnalyzePage from './AnalyzePage';

vi.mock('../services/api', () => ({
  analyzeVideo: vi.fn(),
  ApiError: class ApiError extends Error {
    statusCode: number;
    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
      this.name = 'ApiError';
    }
  },
}));

vi.mock('../components/VideoUploader', () => ({
  default: ({ onUploadComplete }: { onUploadComplete: (key: string, name: string) => void }) => (
    <button data-testid="mock-uploader" onClick={() => onUploadComplete('uploads/user1/123_test.mp4', 'test.mp4')}>
      Mock Upload
    </button>
  ),
}));

import { analyzeVideo, ApiError } from '../services/api';
const mockAnalyzeVideo = vi.mocked(analyzeVideo);

const MOCK_RESULT = {
  reportId: 'rpt-001',
  decision: 'APPROVE' as const,
  decisionReasoning: 'Content is compliant',
  description: 'Test video',
  compliance: { status: 'PASS', reasoning: 'No violations' },
  product: { status: 'ON_BRIEF', reasoning: 'Product visible' },
  disclosure: { status: 'PRESENT', reasoning: 'Disclosure found' },
  campaignRelevance: { score: 0.9, label: 'ON_BRIEF', reasoning: 'Relevant' },
  policyViolations: [],
  analyzedAt: '2024-01-01T00:00:00Z',
};

describe('AnalyzePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders page title and region selector', () => {
    render(<AnalyzePage />);
    expect(screen.getByText('Video Compliance Analysis')).toBeInTheDocument();
    expect(screen.getByLabelText('Region:')).toBeInTheDocument();
  });

  it('has all four region options', () => {
    render(<AnalyzePage />);
    const select = screen.getByLabelText('Region:') as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(['global', 'north_america', 'western_europe', 'east_asia']);
  });

  it('disables analyze button before upload', () => {
    render(<AnalyzePage />);
    expect(screen.getByRole('button', { name: /analyze/i })).toBeDisabled();
  });

  it('enables analyze button after upload completes', () => {
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    expect(screen.getByText('Uploaded: test.mp4')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analyze/i })).toBeEnabled();
  });

  it('shows loading state during analysis', async () => {
    mockAnalyzeVideo.mockImplementation(() => new Promise(() => {})); // never resolves
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));
    expect(screen.getByText(/analyzing video/i)).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('displays analysis results on success', async () => {
    mockAnalyzeVideo.mockResolvedValue(MOCK_RESULT);
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByText('Decision: APPROVE')).toBeInTheDocument();
    });
    expect(screen.getByText('PASS')).toBeInTheDocument();
    expect(screen.getByText('ON_BRIEF')).toBeInTheDocument();
    expect(screen.getByText('PRESENT')).toBeInTheDocument();
  });

  it('calls analyzeVideo with correct s3Key and region', async () => {
    mockAnalyzeVideo.mockResolvedValue(MOCK_RESULT);
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.change(screen.getByLabelText('Region:'), { target: { value: 'east_asia' } });
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(mockAnalyzeVideo).toHaveBeenCalledWith({
        s3Key: 'uploads/user1/123_test.mp4',
        region: 'east_asia',
      });
    });
  });

  it('shows error message on API failure', async () => {
    mockAnalyzeVideo.mockRejectedValue(new ApiError(500, 'Internal server error'));
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Internal server error');
    });
  });

  it('shows friendly message on 503 error', async () => {
    mockAnalyzeVideo.mockRejectedValue(new ApiError(503, 'Service unavailable'));
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Service temporarily unavailable');
    });
  });

  it('displays policy violations when present', async () => {
    const resultWithViolations = {
      ...MOCK_RESULT,
      decision: 'BLOCK' as const,
      policyViolations: [
        { category: 'hate_harassment', severity: 'high', timestamp_start: 10, timestamp_end: 25, evidence: 'Offensive content detected' },
      ],
    };
    mockAnalyzeVideo.mockResolvedValue(resultWithViolations);
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByText('Policy Violations (1)')).toBeInTheDocument();
    });
    expect(screen.getByText('hate_harassment')).toBeInTheDocument();
    expect(screen.getByText('Offensive content detected')).toBeInTheDocument();
    expect(screen.getByText('10s - 25s')).toBeInTheDocument();
  });

  it('renders JSON download button after results', async () => {
    mockAnalyzeVideo.mockResolvedValue(MOCK_RESULT);
    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /download json/i })).toBeInTheDocument();
    });
  });

  it('triggers JSON download on button click', async () => {
    mockAnalyzeVideo.mockResolvedValue(MOCK_RESULT);
    const createObjectURL = vi.fn(() => 'blob:test');
    const revokeObjectURL = vi.fn();
    global.URL.createObjectURL = createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURL;

    const appendSpy = vi.spyOn(document.body, 'appendChild');

    render(<AnalyzePage />);
    fireEvent.click(screen.getByTestId('mock-uploader'));
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /download json/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /download json/i }));
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();
    const anchor = appendSpy.mock.calls.find(
      (call) => (call[0] as HTMLElement).tagName === 'A',
    );
    expect(anchor).toBeDefined();
    appendSpy.mockRestore();
  });
});
