import {MissingDataWorkspace} from '@/components/missing/missing-data-workspace';

export default async function MissingPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <MissingDataWorkspace projectId={projectId} />;
}
