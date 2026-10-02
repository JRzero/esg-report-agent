import {GriWorkspace} from '@/components/gri/gri-workspace';

export default async function GriPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <GriWorkspace projectId={projectId} />;
}
