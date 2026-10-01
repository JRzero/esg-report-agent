import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {
  AIAction,
  CitationMarker,
  FactCard,
  GRICoverage,
  MissingItemCard,
} from './index';

describe('ESG domain component foundation', () => {
  it('renders Fact, GRI and Missing Data states', () => {
    render(
      <>
        <FactCard
          name="Employee total"
          value={1287}
          unit="people"
          status="CONFIRMED"
          evidenceCount={2}
        />
        <GRICoverage
          code="GRI 2-7"
          title="Employees"
          covered={3}
          total={4}
          status="PARTIAL"
        />
        <MissingItemCard
          name="Gender breakdown"
          description="Required data is missing."
          priority="HIGH"
          status="REQUESTED"
        />
      </>,
    );

    expect(screen.getByText('Employee total')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('Gender breakdown')).toBeInTheDocument();
  });

  it('uses Astryx actions for citation and AI commands', () => {
    render(
      <>
        <CitationMarker index={1} label="employees.xlsx · B18" />
        <AIAction actions={['rewrite', 'regenerate-from-evidence']} />
      </>,
    );

    expect(screen.getByRole('button', {name: /引用 1/})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: '改写'})).toBeInTheDocument();
    expect(
      screen.getByRole('button', {name: '根据证据重新生成'}),
    ).toBeInTheDocument();
  });
});
