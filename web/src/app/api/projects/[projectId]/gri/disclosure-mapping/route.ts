import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  _request: Request,
  {params}: {params: Promise<{projectId: string}>},
) {
  const {projectId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/projects/${projectId}/ai/disclosure-mapping`,
      {method: 'POST'},
    ),
  );
}
