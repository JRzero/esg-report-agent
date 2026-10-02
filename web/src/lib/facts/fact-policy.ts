import type {Fact, FactStatus, FactUpdateInput} from '@/lib/api/types';

export const factStatusPresentation: Record<
  FactStatus,
  {label: string; badge: 'warning' | 'green' | 'error' | 'neutral'}
> = {
  PENDING: {label: '待确认', badge: 'warning'},
  CONFIRMED: {label: '已确认', badge: 'green'},
  CONFLICT: {label: '冲突', badge: 'error'},
  REJECTED: {label: '已拒绝', badge: 'neutral'},
};

export function formatFactValue(fact: Fact): string {
  switch (fact.value_type) {
    case 'NUMBER':
      return fact.number_value == null ? '—' : String(fact.number_value);
    case 'TEXT':
      return fact.text_value ?? '—';
    case 'BOOLEAN':
      return fact.boolean_value == null ? '—' : fact.boolean_value ? '是' : '否';
    case 'DATE':
      return fact.date_value ?? '—';
    case 'JSON':
      return fact.json_value == null
        ? '—'
        : JSON.stringify(fact.json_value, null, 2);
  }
}

export function formatFactPeriod(fact: Fact): string {
  if (!fact.period_start && !fact.period_end) return '未指定期间';
  if (fact.period_start === fact.period_end) return fact.period_start ?? '未指定期间';
  return [fact.period_start ?? '…', fact.period_end ?? '…'].join(' – ');
}

export function canEditFact(fact: Fact) {
  return fact.status === 'PENDING' || fact.status === 'CONFLICT';
}

export function canDirectDecision(fact: Fact) {
  return fact.status === 'PENDING';
}

export type FactEditValues = {
  name: string;
  value: string;
  unit: string;
  periodStart: string;
  periodEnd: string;
  entityScope: string;
};

export type FactEditResult =
  | {ok: true; value: FactUpdateInput}
  | {ok: false; message: string};

export function factToEditValues(fact: Fact): FactEditValues {
  let value = '';
  switch (fact.value_type) {
    case 'NUMBER':
      value = fact.number_value == null ? '' : String(fact.number_value);
      break;
    case 'TEXT':
      value = fact.text_value ?? '';
      break;
    case 'BOOLEAN':
      value = fact.boolean_value == null ? '' : String(fact.boolean_value);
      break;
    case 'DATE':
      value = fact.date_value ?? '';
      break;
    case 'JSON':
      value = fact.json_value == null ? '' : JSON.stringify(fact.json_value, null, 2);
      break;
  }
  return {
    name: fact.name,
    value,
    unit: fact.unit ?? '',
    periodStart: fact.period_start ?? '',
    periodEnd: fact.period_end ?? '',
    entityScope: fact.entity_scope ?? '',
  };
}

export function buildFactUpdateInput(
  fact: Fact,
  values: FactEditValues,
): FactEditResult {
  if (!canEditFact(fact)) {
    return {ok: false, message: '当前 Fact 状态不允许编辑'};
  }

  const update: FactUpdateInput = {
    unit: values.unit.trim() || null,
  };

  if (fact.status === 'PENDING') {
    if (!values.name.trim()) return {ok: false, message: 'Fact 名称不能为空'};
    if (
      values.periodStart &&
      values.periodEnd &&
      values.periodStart > values.periodEnd
    ) {
      return {ok: false, message: '开始日期不能晚于结束日期'};
    }
    update.name = values.name.trim();
    update.period_start = values.periodStart || null;
    update.period_end = values.periodEnd || null;
    update.entity_scope = values.entityScope.trim() || null;
  }

  switch (fact.value_type) {
    case 'NUMBER': {
      if (!values.value.trim()) return {ok: false, message: '请输入数值'};
      const number = Number(values.value.replaceAll(',', ''));
      if (!Number.isFinite(number)) return {ok: false, message: '请输入有效数值'};
      update.number_value = number;
      update.raw_value = values.value.trim();
      break;
    }
    case 'TEXT':
      if (!values.value.trim()) return {ok: false, message: '请输入文本值'};
      update.text_value = values.value;
      update.raw_value = values.value;
      break;
    case 'BOOLEAN':
      if (!['true', 'false'].includes(values.value)) {
        return {ok: false, message: '布尔值必须为 true 或 false'};
      }
      update.boolean_value = values.value === 'true';
      update.raw_value = values.value;
      break;
    case 'DATE':
      if (!/^\d{4}-\d{2}-\d{2}$/.test(values.value)) {
        return {ok: false, message: '日期必须为 YYYY-MM-DD'};
      }
      update.date_value = values.value;
      update.raw_value = values.value;
      break;
    case 'JSON':
      try {
        const parsed = JSON.parse(values.value) as unknown;
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          return {ok: false, message: 'JSON Fact 必须是对象'};
        }
        update.json_value = parsed as Record<string, unknown>;
        update.raw_value = values.value;
      } catch {
        return {ok: false, message: '请输入有效 JSON'};
      }
      break;
  }

  return {ok: true, value: update};
}
