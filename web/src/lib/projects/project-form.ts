import type {ProjectCreateInput} from '@/lib/api/types';

export type ProjectFormValues = {
  companyId: string;
  name: string;
  reportYear: string;
  periodStart: string;
  periodEnd: string;
};

export type ProjectFormResult =
  | {ok: true; value: ProjectCreateInput}
  | {ok: false; message: string};

const isoDate = /^\d{4}-\d{2}-\d{2}$/;

export function buildProjectCreateInput(
  values: ProjectFormValues,
): ProjectFormResult {
  const name = values.name.trim();
  if (!values.companyId) return {ok: false, message: '请选择企业'};
  if (!name) return {ok: false, message: '请输入项目名称'};

  const year = Number(values.reportYear);
  if (!Number.isInteger(year) || year < 2000 || year > 2200) {
    return {ok: false, message: '报告年度必须在 2000–2200 之间'};
  }

  if (!isoDate.test(values.periodStart) || !isoDate.test(values.periodEnd)) {
    return {ok: false, message: '请选择有效的报告周期'};
  }

  if (values.periodStart > values.periodEnd) {
    return {ok: false, message: '报告开始日期不能晚于结束日期'};
  }

  return {
    ok: true,
    value: {
      company_id: values.companyId,
      name,
      report_year: year,
      period_start: values.periodStart,
      period_end: values.periodEnd,
    },
  };
}
