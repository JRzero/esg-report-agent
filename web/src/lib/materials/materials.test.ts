import {describe, expect, it} from 'vitest';
import type {DocumentAnchor} from '@/lib/api/types';
import {formatAnchorLocator} from './anchor-locator';
import {canExtractFacts} from './source-policy';

function anchor(
  patch: Partial<DocumentAnchor>,
): DocumentAnchor {
  return {
    id: 'a1',
    tenant_id: 't1',
    project_id: 'p1',
    document_version_id: 'v1',
    anchor_type: 'PLAIN_TEXT',
    page_start: null,
    page_end: null,
    sheet_name: null,
    cell_range: null,
    heading_path: null,
    paragraph_start: null,
    paragraph_end: null,
    slide_number: null,
    bbox: null,
    raw_text: 'text',
    normalized_text: null,
    content_hash: 'hash',
    metadata: {},
    ...patch,
  };
}

describe('material source boundary', () => {
  it('never allows Reference or Standard Fact extraction', () => {
    expect(canExtractFacts('EVIDENCE')).toBe(true);
    expect(canExtractFacts('HISTORICAL')).toBe(true);
    expect(canExtractFacts('REFERENCE')).toBe(false);
    expect(canExtractFacts('STANDARD')).toBe(false);
  });
});

describe('formatAnchorLocator', () => {
  it('formats Excel coordinates', () => {
    expect(
      formatAnchorLocator(
        anchor({anchor_type: 'EXCEL_CELL', sheet_name: '员工统计', cell_range: 'B18'}),
      ),
    ).toBe('Sheet: 员工统计 · Cell: B18');
  });

  it('formats PDF, Word and PPT coordinates', () => {
    expect(formatAnchorLocator(anchor({anchor_type: 'PDF_TEXT', page_start: 23}))).toBe(
      'Page 23',
    );
    expect(
      formatAnchorLocator(
        anchor({
          anchor_type: 'DOCX_PARAGRAPH',
          heading_path: ['社会', '员工发展'],
          paragraph_start: 12,
        }),
      ),
    ).toBe('社会 › 员工发展');
    expect(
      formatAnchorLocator(anchor({anchor_type: 'PPT_TEXT', slide_number: 8})),
    ).toBe('Slide 8');
  });
});
