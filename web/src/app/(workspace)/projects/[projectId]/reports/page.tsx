import {ReportList} from '@/components/reports/report-list';

export default async function ReportsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ReportList projectId={projectId} />;
}
