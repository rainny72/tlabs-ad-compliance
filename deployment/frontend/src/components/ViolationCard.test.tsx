import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ViolationCard from './ViolationCard';
import type { PolicyViolation } from '../services/api';

function makeViolation(overrides: Partial<PolicyViolation> = {}): PolicyViolation {
  return {
    category: 'hate_harassment',
    severity: 'high',
    timestamp_start: 10.5,
    timestamp_end: 15.2,
    evidence: 'Offensive language detected in speech segment.',
    ...overrides,
  };
}

describe('ViolationCard', () => {
  it('renders category name', () => {
    render(<ViolationCard violation={makeViolation()} />);
    expect(screen.getByTestId('violation-category')).toHaveTextContent('hate_harassment');
  });

  it('renders severity with correct color for critical', () => {
    render(<ViolationCard violation={makeViolation({ severity: 'critical' })} />);
    const badge = screen.getByTestId('violation-severity');
    expect(badge).toHaveTextContent('critical');
    expect(badge).toHaveStyle({ backgroundColor: '#f44336' });
  });

  it('renders severity with correct color for high', () => {
    render(<ViolationCard violation={makeViolation({ severity: 'high' })} />);
    const badge = screen.getByTestId('violation-severity');
    expect(badge).toHaveTextContent('high');
    expect(badge).toHaveStyle({ backgroundColor: '#ff9800' });
  });

  it('renders severity with correct color for medium', () => {
    render(<ViolationCard violation={makeViolation({ severity: 'medium' })} />);
    const badge = screen.getByTestId('violation-severity');
    expect(badge).toHaveTextContent('medium');
    expect(badge).toHaveStyle({ backgroundColor: '#ffc107' });
  });

  it('renders severity with correct color for low', () => {
    render(<ViolationCard violation={makeViolation({ severity: 'low' })} />);
    const badge = screen.getByTestId('violation-severity');
    expect(badge).toHaveTextContent('low');
    expect(badge).toHaveStyle({ backgroundColor: '#4caf50' });
  });

  it('renders timestamp range in seconds format', () => {
    render(<ViolationCard violation={makeViolation({ timestamp_start: 10.5, timestamp_end: 15.2 })} />);
    expect(screen.getByTestId('violation-timestamp')).toHaveTextContent('10.5s - 15.2s');
  });

  it('renders evidence text', () => {
    render(<ViolationCard violation={makeViolation({ evidence: 'Drug reference found.' })} />);
    expect(screen.getByTestId('violation-evidence')).toHaveTextContent('Drug reference found.');
  });

  it('renders all fields present in the output', () => {
    const v = makeViolation({
      category: 'profanity_explicit',
      severity: 'medium',
      timestamp_start: 0,
      timestamp_end: 5,
      evidence: 'Explicit content detected.',
    });
    render(<ViolationCard violation={v} />);
    expect(screen.getByTestId('violation-card')).toBeInTheDocument();
    expect(screen.getByTestId('violation-category')).toHaveTextContent('profanity_explicit');
    expect(screen.getByTestId('violation-severity')).toHaveTextContent('medium');
    expect(screen.getByTestId('violation-timestamp')).toHaveTextContent('0s - 5s');
    expect(screen.getByTestId('violation-evidence')).toHaveTextContent('Explicit content detected.');
  });
});
