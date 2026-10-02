import {describe, expect, it} from 'vitest';
import type {ProjectDisclosure, ProjectRequirement} from '@/lib/api/types';
import {
  countDisclosureStatuses,
  effectiveDisclosureStatus,
  requirementMetricCodes,
} from './gri-policy';

function disclosure(
  patch: Partial<ProjectDisclosure> = {},
): ProjectDisclosure {
  return {
    id: 'pd1',
    disclosure_id: 'd1',
    code: 'GRI 2-7',
    title: 'Employees',
    description: null,
    topic_code: null,
    applicability: 'APPLICABLE',
    coverage_status: 'MISSING',
    notes: null,
    ...patch,
  };
}

describe('GRI presentation policy', () => {
  it('lets applicability override coverage display', () => {
    expect(
      effectiveDisclosureStatus(
        disclosure({
          applicability: 'NOT_APPLICABLE',
          coverage_status: 'COVERED',
        }),
      ),
    ).toBe('NOT_APPLICABLE');
  });

  it('counts effective disclosure statuses', () => {
    expect(
      countDisclosureStatuses([
        disclosure({id: '1', coverage_status: 'COVERED'}),
        disclosure({id: '2', coverage_status: 'PARTIAL'}),
        disclosure({id: '3', coverage_status: 'MISSING'}),
        disclosure({
          id: '4',
          applicability: 'NOT_APPLICABLE',
          coverage_status: 'MISSING',
        }),
      ]),
    ).toEqual({
      TOTAL: 4,
      COVERED: 1,
      PARTIAL: 1,
      MISSING: 1,
      NOT_APPLICABLE: 1,
    });
  });

  it('extracts only string metric codes', () => {
    const requirement = {
      required_data_json: {
        metric_codes: ['EMPLOYEE_TOTAL', 123, null],
      },
    } as unknown as ProjectRequirement;
    expect(requirementMetricCodes(requirement)).toEqual(['EMPLOYEE_TOTAL']);
  });
});
