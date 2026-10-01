'use client';

import {useState, type FormEvent} from 'react';
import {useRouter} from 'next/navigation';
import {Button} from '@astryxdesign/core/Button';
import {Selector} from '@astryxdesign/core/Selector';
import {TextInput} from '@astryxdesign/core/TextInput';
import {ApiError} from '@/lib/api/client';
import {useCompanies, useCreateProject} from '@/lib/api/queries';
import {
  buildProjectCreateInput,
  type ProjectFormValues,
} from '@/lib/projects/project-form';

function initialValues(): ProjectFormValues {
  const year = String(new Date().getUTCFullYear());
  return {
    companyId: '',
    name: '',
    reportYear: year,
    periodStart: `${year}-01-01`,
    periodEnd: `${year}-12-31`,
  };
}

export function ProjectCreateForm() {
  const router = useRouter();
  const companies = useCompanies();
  const createProject = useCreateProject();
  const [values, setValues] = useState<ProjectFormValues>(initialValues);
  const [validationError, setValidationError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setValidationError('');

    const result = buildProjectCreateInput(values);
    if (!result.ok) {
      setValidationError(result.message);
      return;
    }

    try {
      const project = await createProject.mutateAsync(result.value);
      router.replace(`/projects/${project.id}`);
    } catch (caught) {
      setValidationError(
        caught instanceof ApiError
          ? caught.message
          : '创建项目失败，请重试。',
      );
    }
  }

  const options = (companies.data ?? []).map((company) => ({
    value: company.id,
    label: company.name,
    description: company.short_name ?? company.region ?? undefined,
  }));

  return (
    <form onSubmit={submit} className="max-w-2xl">
      <div className="grid gap-5">
        <Selector
          label="企业"
          options={options}
          value={values.companyId}
          onChange={(companyId) =>
            setValues((current) => ({...current, companyId}))
          }
          hasSearch={options.length > 8}
          searchPlaceholder="搜索企业"
          emptyText="当前租户暂无企业，请先通过 Service 管理企业。"
        />

        <TextInput
          label="项目名称"
          value={values.name}
          onChange={(name) => setValues((current) => ({...current, name}))}
          placeholder="例如：XX集团 2026 ESG 报告"
          width="100%"
          isRequired
        />

        <TextInput
          label="报告年度"
          value={values.reportYear}
          onChange={(reportYear) =>
            setValues((current) => ({...current, reportYear}))
          }
          width={180}
          isRequired
        />

        <div className="grid gap-4 md:grid-cols-2">
          <TextInput
            label="报告开始日期"
            value={values.periodStart}
            onChange={(periodStart) =>
              setValues((current) => ({...current, periodStart}))
            }
            description="YYYY-MM-DD"
            width="100%"
            isRequired
          />
          <TextInput
            label="报告结束日期"
            value={values.periodEnd}
            onChange={(periodEnd) =>
              setValues((current) => ({...current, periodEnd}))
            }
            description="YYYY-MM-DD"
            width="100%"
            isRequired
          />
        </div>

        {validationError ? (
          <div
            className="rounded-md border px-3 py-2 text-sm"
            role="alert">
            {validationError}
          </div>
        ) : null}

        <div className="flex gap-3">
          <Button
            label="创建项目"
            type="submit"
            variant="primary"
            isLoading={createProject.isPending}
            isDisabled={companies.isLoading || options.length === 0}
          />
          <Button label="取消" variant="secondary" href="/projects" />
        </div>
      </div>
    </form>
  );
}
