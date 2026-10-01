'use client';

import {useEffect, useMemo} from 'react';
import {useRouter} from 'next/navigation';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {ApiError} from '@/lib/api/client';
import {useCompanies, useProjects} from '@/lib/api/queries';

export function ProjectList() {
  const router = useRouter();
  const projects = useProjects();
  const companies = useCompanies();

  useEffect(() => {
    if (
      projects.error instanceof ApiError &&
      projects.error.status === 401
    ) {
      router.replace('/login');
    }
  }, [projects.error, router]);

  const companyNames = useMemo(
    () =>
      new Map(
        (companies.data ?? []).map((company) => [company.id, company.name]),
      ),
    [companies.data],
  );

  if (projects.isLoading) {
    return <div className="py-12 text-sm opacity-60">正在加载项目…</div>;
  }

  if (projects.error) {
    return (
      <div className="py-12">
        <h2 className="text-base font-semibold">项目加载失败</h2>
        <p className="mt-2 text-sm opacity-65">
          {projects.error instanceof Error
            ? projects.error.message
            : '无法读取项目列表。'}
        </p>
        <div className="mt-4">
          <Button
            label="重试"
            variant="secondary"
            onClick={() => void projects.refetch()}
          />
        </div>
      </div>
    );
  }

  if (!projects.data?.length) {
    return (
      <EmptyState
        title="还没有 ESG 项目"
        description="创建第一个企业 ESG 报告项目，之后的资料、Fact、GRI 和报告都归属于项目。"
        headingLevel={2}
        actions={
          <Button
            label="创建项目"
            variant="primary"
            href="/projects/new"
          />
        }
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      {projects.data.map((project) => (
        <Card key={project.id} padding={4}>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{project.name}</div>
              <div className="mt-1 text-xs opacity-60">
                {companyNames.get(project.company_id) ?? '企业信息加载中'}
              </div>
            </div>
            {project.status !== 'ACTIVE' ? (
              <Badge label={project.status} variant="neutral" />
            ) : null}
          </div>

          <div className="mt-5 grid grid-cols-2 gap-4 text-xs">
            <div>
              <div className="opacity-50">报告年度</div>
              <div className="mt-1 font-medium">{project.report_year}</div>
            </div>
            <div>
              <div className="opacity-50">报告周期</div>
              <div className="mt-1 font-medium">
                {project.period_start} – {project.period_end}
              </div>
            </div>
          </div>

          <div className="mt-5">
            <Button
              label="进入项目"
              variant="secondary"
              href={`/projects/${project.id}`}
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
