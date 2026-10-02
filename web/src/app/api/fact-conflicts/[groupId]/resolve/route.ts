import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  request: Request,
  {params}: {params: Promise<{groupId: string}>},
) {
  const {groupId} = await params;
  const body = (await request.json()) as {fact_id?: string};
  if (!body.fact_id) {
    return Response.json(
      {error: {code: 'VALIDATION_FAILED', message: 'fact_id is required'}},
      {status: 422},
    );
  }
  const query = new URLSearchParams({fact_id: body.fact_id});
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/fact-conflicts/${groupId}/resolve?${query.toString()}`,
      {method: 'POST'},
    ),
  );
}
