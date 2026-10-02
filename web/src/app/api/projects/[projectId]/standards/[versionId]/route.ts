import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{projectId: string; versionId: string}>;
  },
) {
  const {projectId, versionId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/projects/${projectId}/standards/${versionId}`,
      {method: 'POST'},
    ),
  );
}
