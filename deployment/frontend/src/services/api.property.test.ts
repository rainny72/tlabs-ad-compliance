import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';

// Mock aws-amplify/auth
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn().mockResolvedValue({
    tokens: { idToken: { toString: () => 'mock-token' } },
  }),
}));

// Must import AFTER mocking
import { analyzeVideo, ApiError } from './api';
import type { AnalyzeResponse } from './api';

const MOCK_RESULT: AnalyzeResponse = {
  reportId: 'test-report',
  decision: 'APPROVE',
  decisionReasoning: 'test',
  description: 'test',
  compliance: { status: 'PASS', reasoning: 'ok' },
  product: { status: 'CLEAR', reasoning: 'ok' },
  disclosure: { status: 'PRESENT', reasoning: 'ok' },
  campaignRelevance: { score: 0.9, label: 'ON_BRIEF', reasoning: 'ok' },
  policyViolations: [],
  analyzedAt: '2025-01-01T00:00:00Z',
};

/**
 * Feature: async-analysis, Property 8: Polling 터미널 상태 처리
 *
 * Validates: Requirements 4.3, 4.4
 *
 * For any polling sequence, when the response status is COMPLETED or FAILED,
 * polling stops immediately. COMPLETED returns the analysis result;
 * FAILED throws an ApiError.
 */
describe('Feature: async-analysis, Property 8: Polling 터미널 상태 처리', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  test('COMPLETED/FAILED 시 polling 즉시 중단 (100 iterations)', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fc.constantFrom('PENDING', 'PROCESSING'), { minLength: 0, maxLength: 5 }),
        fc.constantFrom('COMPLETED', 'FAILED'),
        async (pendingStatuses, terminalStatus) => {
          let fetchCallCount = 0;

          const mockFetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
            fetchCallCount++;

            if (options?.method === 'POST') {
              return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ jobId: 'test-job-id', status: 'PENDING' }),
              });
            }

            const pollIndex = fetchCallCount - 2;

            if (pollIndex < pendingStatuses.length) {
              return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({
                  job_id: 'test-job-id',
                  status: pendingStatuses[pollIndex],
                }),
              });
            }

            const terminalResponse: Record<string, unknown> = {
              job_id: 'test-job-id',
              status: terminalStatus,
            };
            if (terminalStatus === 'COMPLETED') {
              terminalResponse.result = {
                report_id: MOCK_RESULT.reportId,
                decision: MOCK_RESULT.decision,
                decision_reasoning: MOCK_RESULT.decisionReasoning,
                description: MOCK_RESULT.description,
                compliance: MOCK_RESULT.compliance,
                product: MOCK_RESULT.product,
                disclosure: MOCK_RESULT.disclosure,
                campaign_relevance: MOCK_RESULT.campaignRelevance,
                policy_violations: MOCK_RESULT.policyViolations,
                analyzed_at: MOCK_RESULT.analyzedAt,
              };
            }
            if (terminalStatus === 'FAILED') {
              terminalResponse.error = 'Analysis failed';
            }

            return Promise.resolve({
              ok: true,
              json: () => Promise.resolve(terminalResponse),
            });
          });

          global.fetch = mockFetch;

          // Capture the promise and immediately attach a catch handler
          // to prevent unhandled rejection warnings
          let resolvedResult: AnalyzeResponse | undefined;
          let rejectedError: unknown;

          const analyzePromise = analyzeVideo(
            { s3Key: 'uploads/test.mp4', region: 'global' },
          ).then(
            (result) => { resolvedResult = result; },
            (error) => { rejectedError = error; },
          );

          // Advance timers for each poll cycle
          const totalPolls = pendingStatuses.length + 1;
          for (let i = 0; i < totalPolls; i++) {
            await vi.advanceTimersByTimeAsync(5000);
          }

          await analyzePromise;

          if (terminalStatus === 'COMPLETED') {
            expect(resolvedResult).toBeDefined();
            expect(resolvedResult!.reportId).toBe(MOCK_RESULT.reportId);
            expect(rejectedError).toBeUndefined();
          } else {
            expect(rejectedError).toBeInstanceOf(ApiError);
            expect(resolvedResult).toBeUndefined();
          }

          // Verify: 1 POST + (pendingStatuses.length + 1) GETs
          const expectedCalls = 1 + pendingStatuses.length + 1;
          expect(mockFetch).toHaveBeenCalledTimes(expectedCalls);
        },
      ),
      { numRuns: 100 },
    );
  });
});
