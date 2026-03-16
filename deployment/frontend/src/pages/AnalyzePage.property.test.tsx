import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import * as fc from 'fast-check';
import AnalyzePage from './AnalyzePage';

// Mock VideoUploader - simple component that calls onUploadComplete
vi.mock('../components/VideoUploader', () => ({
  default: ({ onUploadComplete }: { onUploadComplete: (key: string, filename: string) => void }) => (
    <button data-testid="mock-upload" onClick={() => onUploadComplete('uploads/test.mp4', 'test.mp4')}>
      Upload
    </button>
  ),
}));

// Set up api mocks
const mockAnalyzeVideo = vi.fn();
const mockGetSettings = vi.fn();

vi.mock('../services/api', () => ({
  analyzeVideo: (...args: unknown[]) => mockAnalyzeVideo(...args),
  getSettings: () => mockGetSettings(),
  ApiError: class ApiError extends Error {
    statusCode: number;
    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
      this.name = 'ApiError';
    }
  },
}));

/**
 * Feature: async-analysis, Property 10: Polling 상태 표시
 *
 * **Validates: Requirements 4.1, 4.2**
 *
 * For any polling 중인 상태에서, 프론트엔드는 현재 Job_Status(PENDING 또는 PROCESSING)를
 * 사용자에게 표시해야 한다.
 */
describe('Feature: async-analysis, Property 10: Polling 상태 표시', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetSettings.mockResolvedValue({ backend: 'bedrock' });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    cleanup();
  });

  test('PENDING/PROCESSING 상태를 사용자에게 표시 (100 iterations)', async () => {
    // Property-based test with 100 iterations needs extended timeout
    await fc.assert(
      fc.asyncProperty(
        fc.constantFrom('PENDING', 'PROCESSING'),
        fc.constantFrom('bedrock', 'twelvelabs'),
        async (status, backend) => {
          mockGetSettings.mockResolvedValue({ backend });

          // Mock analyzeVideo to call onStatusChange then hang (never resolve)
          mockAnalyzeVideo.mockImplementation(
            (_request: unknown, onStatusChange?: (s: string) => void) => {
              setTimeout(() => onStatusChange?.(status), 0);
              return new Promise(() => {});
            },
          );

          const { unmount } = render(<AnalyzePage />);

          // Wait for settings to load
          await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
          });

          // Simulate upload
          const uploadBtn = screen.getByTestId('mock-upload');
          await act(async () => {
            fireEvent.click(uploadBtn);
          });

          // Click analyze
          const analyzeBtn = screen.getByRole('button', { name: /run analysis/i });
          await act(async () => {
            fireEvent.click(analyzeBtn);
          });

          // Advance timer to trigger the onStatusChange callback
          await act(async () => {
            await vi.advanceTimersByTimeAsync(100);
          });

          // Verify status text
          if (status === 'PENDING') {
            expect(screen.getByText(/analysis queued, waiting to start/i)).toBeDefined();
          } else if (status === 'PROCESSING') {
            if (backend === 'twelvelabs') {
              expect(screen.getByText(/TwelveLabs API/i)).toBeDefined();
            } else {
              expect(screen.getByText(/Amazon Bedrock/i)).toBeDefined();
            }
          }

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  }, 60_000);
});
