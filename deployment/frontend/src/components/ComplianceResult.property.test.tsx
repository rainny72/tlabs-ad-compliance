import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import ComplianceResult from './ComplianceResult';
import type { AnalyzeResponse } from '../services/api';

// Feature: amplify-serverless-migration, Property 9: 3축 평가 결과 렌더링 완전성

const alphanumArb = fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/);

const axisStatusArb = fc.record({
  status: alphanumArb,
  reasoning: fc.string({ minLength: 1, maxLength: 100 }),
});

const analyzeResponseArb: fc.Arbitrary<AnalyzeResponse> = fc.record({
  reportId: fc.uuid(),
  decision: fc.constantFrom('APPROVE' as const, 'REVIEW' as const, 'BLOCK' as const),
  decisionReasoning: fc.string({ minLength: 1, maxLength: 200 }),
  description: fc.string({ maxLength: 100 }),
  compliance: axisStatusArb,
  product: axisStatusArb,
  disclosure: axisStatusArb,
  campaignRelevance: fc.record({
    score: fc.double({ min: 0, max: 1, noNaN: true }),
    label: fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/),
    reasoning: fc.string({ minLength: 1, maxLength: 100 }),
  }),
  policyViolations: fc.array(
    fc.record({
      category: fc.stringMatching(/^[a-zA-Z0-9]{1,30}$/),
      severity: fc.constantFrom('critical', 'high', 'medium', 'low'),
      timestamp_start: fc.nat({ max: 3600 }),
      timestamp_end: fc.nat({ max: 3600 }),
      evidence: fc.string({ minLength: 1, maxLength: 200 }),
    }),
    { maxLength: 5 },
  ),
  analyzedAt: fc.date().map((d) => d.toISOString()),
});

describe('ComplianceResult Property Tests', () => {
  // **Validates: Requirements 7.5**
  it('renders all three axis statuses for any valid AnalyzeResponse', () => {
    fc.assert(
      fc.property(analyzeResponseArb, (result) => {
        const { container } = render(<ComplianceResult result={result} />);

        // Compliance status must be rendered
        const complianceEl = screen.getByTestId('axis-compliance');
        expect(complianceEl).toHaveTextContent(result.compliance.status);

        // Product status must be rendered
        const productEl = screen.getByTestId('axis-product');
        expect(productEl).toHaveTextContent(result.product.status);

        // Disclosure status must be rendered
        const disclosureEl = screen.getByTestId('axis-disclosure');
        expect(disclosureEl).toHaveTextContent(result.disclosure.status);

        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});
