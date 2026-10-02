import {describe, expect, it} from 'vitest';
import type {Fact} from '@/lib/api/types';
import {
  buildFactUpdateInput,
  canDirectDecision,
  canEditFact,
  formatFactValue,
} from './fact-policy';

function fact(patch: Partial<Fact> = {}): Fact {
  return {
    id: 'f1',
    tenant_id: 't1',
    project_id: 'p1',
    fact_type: 'METRIC',
    metric_definition_id: null,
    semantic_key: 'employee-total',
    name: 'Employee total',
    value_type: 'NUMBER',
    number_value: 1287,
    text_value: null,
    boolean_value: null,
    date_value: null,
    json_value: null,
    raw_value: '1287',
    unit: 'person',
    period_start: '2026-01-01',
    period_end: '2026-12-31',
    entity_scope: 'GROUP',
    dimensions: {},
    status: 'PENDING',
    confidence: 0.98,
    source_type: 'AI',
    confirmed_by: null,
    confirmed_at: null,
    created_at: '2026-10-02T00:00:00Z',
    updated_at: '2026-10-02T00:00:00Z',
    ...patch,
  };
}

describe('Fact policy', () => {
  it('allows direct confirm/reject only for pending facts', () => {
    expect(canDirectDecision(fact())).toBe(true);
    expect(canDirectDecision(fact({status: 'CONFLICT'}))).toBe(false);
    expect(canDirectDecision(fact({status: 'CONFIRMED'}))).toBe(false);
  });

  it('allows edits for pending and conflict candidates only', () => {
    expect(canEditFact(fact())).toBe(true);
    expect(canEditFact(fact({status: 'CONFLICT'}))).toBe(true);
    expect(canEditFact(fact({status: 'CONFIRMED'}))).toBe(false);
    expect(canEditFact(fact({status: 'REJECTED'}))).toBe(false);
  });

  it('normalizes numeric edits', () => {
    const result = buildFactUpdateInput(fact(), {
      name: 'Employee total',
      value: '1,293',
      unit: 'people',
      periodStart: '2026-01-01',
      periodEnd: '2026-12-31',
      entityScope: 'GROUP',
    });
    expect(result).toEqual({
      ok: true,
      value: {
        name: 'Employee total',
        number_value: 1293,
        raw_value: '1,293',
        unit: 'people',
        period_start: '2026-01-01',
        period_end: '2026-12-31',
        entity_scope: 'GROUP',
      },
    });
  });

  it('does not let conflict editing change semantic-key fields', () => {
    const result = buildFactUpdateInput(fact({status: 'CONFLICT'}), {
      name: 'Changed name',
      value: '1293',
      unit: 'people',
      periodStart: '2025-01-01',
      periodEnd: '2025-12-31',
      entityScope: 'SUBSIDIARY',
    });
    expect(result).toEqual({
      ok: true,
      value: {
        number_value: 1293,
        raw_value: '1293',
        unit: 'people',
      },
    });
  });

  it('formats typed values', () => {
    expect(formatFactValue(fact())).toBe('1287');
    expect(formatFactValue(fact({value_type: 'BOOLEAN', number_value: null, boolean_value: false}))).toBe('否');
  });
});
