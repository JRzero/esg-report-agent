'use client';

import {useEffect, useMemo} from 'react';
import {useRouter} from 'next/navigation';
import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import {ApiError} from '@/lib/api/client';
import {useCompanies, useProject} from '@/lib/api/queries';

export function ProjectOverview({projectId}: {projectId: string}) {
  const router = useRouter();
  const project = useProject(projectId);
  const companies = useCompanies();

  useEffect(() => {
    if (project.error instanceof ApiError && project.error.status === 401) {
      router.replace('/login');
    }
  }, [project.error, router]);

  const company = useMemo(
    () =>
      companies.data?.find(
        (item) => item.id === project.data?.company_id,
      ),
    [companies.data, project.data?.company_id],
  );

  if (project.isLoading) {
    return <div className="py-10 text-sm opacity-60">正在加载项目…</div>;
  }

  if (!project.data) {
    return (
      <div className="py-10">
        <h2 className="text-base font-semibold">无法读取项目</h2>
        <p className="mt-2 text-sm opacity-65">
          {project.error instanceof Error
            ? project.error.message
            : '项目不存在或当前成员无权访问。'}
        </p>
      </div>
    );
  }

  return (
    <>
      <header>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{project.data.name}</h1>
          {project.data.status !== 'ACTIVE' ? (
            <Badge label={project.data.status} variant="neutral" />
          ) : null}
        </div>
        <p className="mt-2 text-sm opacity-65">
          {company?.name ?? '企业信息加载中'} · {project.data.report_year} ESG
        </p>
      </header>

      <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card padding={4}>
          <div className="text-xs opacity-50">报告年度</div>
          <div className="mt-2 text-xl font-semibold">
            {project.data.report_year}
          </div>
        </Card>
        <Card padding={4}>
          <div className="text-xs opacity-50">报告周期</div>
          <div className="mt-2 text-sm font-semibold">
            {project.data.period_start}
            <br />
            {project.data.period_end}
          </div>
        </Card>
        <Card padding={4}>
          <div className="text-xs opacity-50">项目状态</div>
          <div className="mt-2 text-xl font-semibold">
            {project.data.status}
          </div>
        </Card>
      </section>

      <section className="mt-8">
        <h2 className="text-base font-semibold">下一步</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 opacity-65">
          项目骨架已经连接真实 Service API。下一阶段从“资料”入口开始实现
          Material Center，并沿 Evidence → Fact → GRI → Report 继续向下。
        </p>
      </section>
    </>
  );
}
