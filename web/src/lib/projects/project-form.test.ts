import {describe, expect, it} from 'vitest';
import {buildProjectCreateInput} from './project-form';

describe('buildProjectCreateInput', () => {
  it('builds the backend ProjectCreate contract', () => {
    const result = buildProjectCreateInput({
      companyId: 'company-1',
      name: ' Example 2026 ESG ',
      reportYear: '2026',
      periodStart: '2026-01-01',
      periodEnd: '2026-12-31',
    });

    expect(result).toEqual({
      ok: true,
      value: {
        company_id: 'company-1',
        name: 'Example 2026 ESG',
        report_year: 2026,
        period_start: '2026-01-01',
        period_end: '2026-12-31',
      },
    });
  });

  it('rejects an inverted reporting period', () => {
    const result = buildProjectCreateInput({
      companyId: 'company-1',
      name: 'ESG',
      reportYear: '2026',
      periodStart: '2026-12-31',
      periodEnd: '2026-01-01',
    });

    expect(result).toEqual({
      ok: false,
      message: '报告开始日期不能晚于结束日期',
    });
  });
});
