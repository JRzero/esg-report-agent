import {describe, expect, it} from 'vitest';
import type {ReportSection, SectionPlanningContext} from '@/lib/api/types';
import {
  buildSectionTree,
  countPlanningContext,
  formatPlanningEvidenceLocator,
} from './report-policy';

function section(
  id: string,
  parentId: string | null,
  sortOrder: number,
): ReportSection {
  return {
    id,
    tenant_id: 't1',
    project_id: 'p1',
    report_id: 'r1',
    parent_id: parentId,
    source_template_section_id: null,
    title: id,
    description: null,
    level: parentId ? 2 : 1,
    sort_order: sortOrder,
    status: 'NOT_STARTED',
    writing_plan: {},
    created_at: '2026-10-02T00:00:00Z',
    updated_at: '2026-10-02T00:00:00Z',
  };
}

describe('report policy', () => {
  it('builds a stable section tree', () => {
    const tree = buildSectionTree([
      section('child', 'root', 2),
      section('root2', null, 2),
      section('root', null, 1),
    ]);
    expect(tree.map((item) => item.id)).toEqual(['root', 'root2']);
    expect(tree[0].children.map((item) => item.id)).toEqual(['child']);
  });

  it('summarizes planning context boundaries', () => {
    const context = {
      disclosures: [{}, {}],
      requirements: [{}],
      facts: [{}, {}, {}],
      evidence: [{}, {}],
      missing_items: [{}],
    } as unknown as SectionPlanningContext;
    expect(countPlanningContext(context)).toEqual({
      disclosures: 2,
      requirements: 1,
      facts: 3,
      evidence: 2,
      missing: 1,
    });
  });

  it('formats evidence locators', () => {
    const evidence = {
      sheet_name: '员工统计',
      cell_range: 'B18',
      page_start: null,
      page_end: null,
      slide_number: null,
      heading_path: null,
      anchor_type: 'EXCEL_CELL',
    } as unknown as SectionPlanningContext['evidence'][number];
    expect(formatPlanningEvidenceLocator(evidence)).toBe(
      'Sheet: 员工统计 · Cell: B18',
    );
  });
});
