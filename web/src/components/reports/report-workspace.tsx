'use client';

import {useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import {useReport, useSections} from '@/lib/api/queries';
import {SectionTree} from './section-tree';
import {SectionPlanningWorkspace} from './section-planning-workspace';

export function ReportWorkspace({
  projectId,
  reportId,
}: {
  projectId: string;
  reportId: string;
}) {
  const report = useReport(reportId);
  const sections = useSections(reportId);
  const [selectedId, setSelectedId] = useState('');

  if (report.isLoading || !report.data) {
    return <div className="py-10 text-sm opacity-60">正在加载 Report…</div>;
  }

  const sectionList = sections.data ?? [];
  const effectiveSelectedId =
    selectedId && sectionList.some((item) => item.id === selectedId)
      ? selectedId
      : sectionList[0]?.id ?? '';

  return (
    <div>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest opacity-45">
            Report Workspace
          </div>
          <h1 className="mt-2 text-2xl font-semibold">{report.data.title}</h1>
          <p className="mt-2 text-sm opacity-60">
            {report.data.language} · 当前阶段只完成 Section Planning，不直接生成正文。
          </p>
        </div>
        <Badge label={report.data.status} variant="neutral" />
      </header>

      <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <SectionTree
          reportId={reportId}
          sections={sectionList}
          selectedId={effectiveSelectedId}
          onSelect={setSelectedId}
        />

        {effectiveSelectedId ? (
          <SectionPlanningWorkspace
            key={effectiveSelectedId}
            projectId={projectId}
            reportId={reportId}
            sectionId={effectiveSelectedId}
          />
        ) : (
          <Card padding={5}>
            <div className="text-sm font-semibold">先创建一个 Section</div>
            <p className="mt-2 text-sm opacity-60">
              Section 是 Disclosure Mapping 和 Writing Plan 的最小工作单元。
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
