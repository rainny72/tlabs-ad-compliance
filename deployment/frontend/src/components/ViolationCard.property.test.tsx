import { render, cleanup, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import ViolationCard from './ViolationCard';
import type { PolicyViolation } from '../services/api';

// Feature: amplify-serverless-migration, Property 10: 위반 정보 렌더링 완전성

const policyViolationArb: fc.Arbitrary<PolicyViolation> = fc.record({
  category: fc.stringMatching(/^[a-zA-Z0-9_]{1,30}$/),
  severity: fc.constantFrom('critical', 'high', 'medium', 'low'),
  timestamp_start: fc.nat({ max: 3600 }),
  timestamp_end: fc.nat({ max: 3600 }),
  evidence: fc.stringMatching(/^[a-zA-Z0-9 .,!?]{1,200}$/).filter((s) => s.trim().length > 0),
});

describe('ViolationCard Property Tests', () => {
  // **Validates: Requirements 7.8**
  it('renders category, severity, timestamps, and evidence for any valid PolicyViolation', () => {
    fc.assert(
      fc.property(policyViolationArb, (violation) => {
        const { container } = render(<ViolationCard violation={violation} />);
        const card = within(container);

        // Category must be rendered
        const categoryEl = card.getByTestId('violation-category');
        expect(categoryEl).toHaveTextContent(violation.category);

        // Severity must be rendered
        const severityEl = card.getByTestId('violation-severity');
        expect(severityEl).toHaveTextContent(violation.severity);

        // Timestamps must be rendered
        const timestampEl = card.getByTestId('violation-timestamp');
        expect(timestampEl).toHaveTextContent(`${violation.timestamp_start}s`);
        expect(timestampEl).toHaveTextContent(`${violation.timestamp_end}s`);

        // Evidence must be rendered
        const evidenceEl = card.getByTestId('violation-evidence');
        expect(evidenceEl.textContent).toContain(violation.evidence);

        cleanup();
      }),
      { numRuns: 100 },
    );
  });
});
