import {FactCenter} from '@/components/facts/fact-center';

export default async function FactsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <FactCenter projectId={projectId} />;
}
