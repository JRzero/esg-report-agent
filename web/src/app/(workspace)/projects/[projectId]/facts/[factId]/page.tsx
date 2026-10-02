import Link from 'next/link';
import {FactDetail} from '@/components/facts/fact-detail';

export default async function FactPage({
  params,
}: {
  params: Promise<{projectId: string; factId: string}>;
}) {
  const {projectId, factId} = await params;
  return (
    <div>
      <div className="mb-5">
        <Link
          href={`/projects/${projectId}/facts`}
          className="text-sm opacity-60 hover:opacity-100">
          ← 返回 Fact Center
        </Link>
      </div>
      <FactDetail projectId={projectId} factId={factId} />
    </div>
  );
}
