import Link from 'next/link';
import {DisclosureDetail} from '@/components/gri/disclosure-detail';

export default async function DisclosurePage({
  params,
}: {
  params: Promise<{projectId: string; projectDisclosureId: string}>;
}) {
  const {projectId, projectDisclosureId} = await params;

  return (
    <div>
      <div className="mb-5">
        <Link
          href={`/projects/${projectId}/gri`}
          className="text-sm opacity-60 hover:opacity-100">
          ← 返回 GRI Workspace
        </Link>
      </div>
      <DisclosureDetail
        projectId={projectId}
        projectDisclosureId={projectDisclosureId}
      />
    </div>
  );
}
