import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {EvidenceCard} from './evidence-card';

describe('EvidenceCard', () => {
  it('marks Reference as non-factual source', () => {
    render(
      <EvidenceCard
        sourceType="REFERENCE"
        fileName="peer-report.pdf"
        locator="Page 12"
        excerpt="Example style"
      />,
    );

    expect(screen.getByText('Reference')).toBeInTheDocument();
    expect(screen.getByText(/不得作为当前企业事实证据/)).toBeInTheDocument();
  });

  it('does not show the Reference warning for enterprise Evidence', () => {
    render(
      <EvidenceCard
        sourceType="EVIDENCE"
        fileName="employees.xlsx"
        locator="B18"
        excerpt="1287"
      />,
    );

    expect(screen.getByText('Evidence')).toBeInTheDocument();
    expect(
      screen.queryByText(/不得作为当前企业事实证据/),
    ).not.toBeInTheDocument();
  });
});
