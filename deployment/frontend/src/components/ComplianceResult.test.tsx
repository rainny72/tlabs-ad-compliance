import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ComplianceResult from './ComplianceResult';
import type { AnalyzeResponse } from '../services/api';

function makeResult(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    reportId: 'rpt-001',
    decision: 'APPROVE',
    decisionReasoning: 'Content meets all policy requirements.',
    description: 'A product demo video.',
    compliance: { status: 'PASS', reasoning: 'No violations detected.' },
    product: { status: 'ON_BRIEF', reasoning: 'Product clearly visible.' },
    disclosure: { status: 'PRESENT', reasoning: 'Disclosure shown at start.' },
    campaignRelevance: { score: 0.92, label: 'ON_BRIEF', reasoning: 'Highly relevant.' },
    policyViolations: [],
    analyzedAt: '2024-06-01T12:00:00Z',
    ...overrides,
  };
}

describe('ComplianceResult', () => {
  it('renders decision banner with APPROVE text and green background', () => {
    render(<ComplianceResult result={makeResult()} />);
    const banner = screen.getByTestId('decision-banner');
    expect(banner).toHaveTextContent('Decision: APPROVE');
    expect(banner).toHaveStyle({ backgroundColor: '#4caf50' });
  });

  it('renders REVIEW decision with orange background', () => {
    render(<ComplianceResult result={makeResult({ decision: 'REVIEW' })} />);
    const banner = screen.getByTestId('decision-banner');
    expect(banner).toHaveTextContent('Decision: REVIEW');
    expect(banner).toHaveStyle({ backgroundColor: '#ff9800' });
  });

  it('renders BLOCK decision with red background', () => {
    render(<ComplianceResult result={makeResult({ decision: 'BLOCK' })} />);
    const banner = screen.getByTestId('decision-banner');
    expect(banner).toHaveTextContent('Decision: BLOCK');
    expect(banner).toHaveStyle({ backgroundColor: '#f44336' });
  });

  it('renders decision reasoning text', () => {
    render(<ComplianceResult result={makeResult()} />);
    expect(screen.getByTestId('decision-reasoning')).toHaveTextContent(
      'Content meets all policy requirements.',
    );
  });

  it('renders all 3 axis statuses', () => {
    render(<ComplianceResult result={makeResult()} />);

    const compliance = screen.getByTestId('axis-compliance');
    expect(compliance).toHaveTextContent('Compliance');
    expect(compliance).toHaveTextContent('PASS');
    expect(compliance).toHaveTextContent('No violations detected.');

    const product = screen.getByTestId('axis-product');
    expect(product).toHaveTextContent('Product');
    expect(product).toHaveTextContent('ON_BRIEF');
    expect(product).toHaveTextContent('Product clearly visible.');

    const disclosure = screen.getByTestId('axis-disclosure');
    expect(disclosure).toHaveTextContent('Disclosure');
    expect(disclosure).toHaveTextContent('PRESENT');
    expect(disclosure).toHaveTextContent('Disclosure shown at start.');
  });

  it('shows campaign relevance score and label', () => {
    render(<ComplianceResult result={makeResult()} />);
    const relevance = screen.getByTestId('campaign-relevance');
    expect(relevance).toHaveTextContent('Campaign Relevance');
    expect(relevance).toHaveTextContent('0.92');
    expect(relevance).toHaveTextContent('ON_BRIEF');
    expect(relevance).toHaveTextContent('Highly relevant.');
  });

  it('shows policy violations count', () => {
    const violations = [
      { category: 'profanity_explicit', severity: 'high', timestamp_start: 10, timestamp_end: 15, evidence: 'Bad word' },
      { category: 'drugs_illegal', severity: 'medium', timestamp_start: 20, timestamp_end: 25, evidence: 'Drug ref' },
    ];
    render(<ComplianceResult result={makeResult({ policyViolations: violations })} />);
    expect(screen.getByTestId('violations-summary')).toHaveTextContent('Policy Violations: 2');
  });

  it('shows zero violations count when none exist', () => {
    render(<ComplianceResult result={makeResult({ policyViolations: [] })} />);
    expect(screen.getByTestId('violations-summary')).toHaveTextContent('Policy Violations: 0');
  });
});
