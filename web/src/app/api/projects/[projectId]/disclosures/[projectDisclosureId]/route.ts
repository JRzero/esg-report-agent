import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{projectId: string; projectDisclosureId: string}>;
  },
) {
  const {projectId, projectDisclosureId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/projects/${projectId}/disclosures/${projectDisclosureId}`,
    ),
  );
}

export async function PATCH(
  request: Request,
  {
    params,
  }: {
    params: Promise<{projectId: string; projectDisclosureId: string}>;
  },
) {
  const {projectId, projectDisclosureId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/projects/${projectId}/disclosures/${projectDisclosureId}`,
      {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: await request.text(),
      },
    ),
  );
}
