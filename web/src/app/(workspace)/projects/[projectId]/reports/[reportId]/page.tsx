import Link from 'next/link';
import {ReportWorkspace} from '@/components/reports/report-workspace';

export default async function ReportPage({
  params,
}: {
  params: Promise<{projectId: string; reportId: string}>;
}) {
  const {projectId, reportId} = await params;

  return (
    <div>
      <div className="mb-5">
        <Link
          href={`/projects/${projectId}/reports`}
          className="text-sm opacity-60 hover:opacity-100">
          ← 返回报告列表
        </Link>
      </div>
      <ReportWorkspace projectId={projectId} reportId={reportId} />
    </div>
  );
}
