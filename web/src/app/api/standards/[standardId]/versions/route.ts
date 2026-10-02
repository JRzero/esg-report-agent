import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{standardId: string}>},
) {
  const {standardId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(
      `/api/v1/standards/${standardId}/versions`,
    ),
  );
}
