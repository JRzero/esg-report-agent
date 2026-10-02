import Link from 'next/link';
import {DocumentEvidenceViewer} from '@/components/materials/document-evidence-viewer';

export default async function MaterialDetailPage({
  params,
}: {
  params: Promise<{projectId: string; documentId: string}>;
}) {
  const {projectId, documentId} = await params;

  return (
    <div>
      <div className="mb-5">
        <Link
          href={`/projects/${projectId}/materials`}
          className="text-sm opacity-60 hover:opacity-100">
          ← 返回资料中心
        </Link>
      </div>
      <DocumentEvidenceViewer projectId={projectId} documentId={documentId} />
    </div>
  );
}
