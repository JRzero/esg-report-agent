import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{projectId: string}>},
) {
  const {projectId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/projects/${projectId}/reports`),
  );
}

export async function POST(
  request: Request,
  {params}: {params: Promise<{projectId: string}>},
) {
  const {projectId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/projects/${projectId}/reports`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: await request.text(),
    }),
  );
}
