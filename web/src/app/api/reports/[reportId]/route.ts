import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function GET(
  _request: Request,
  {params}: {params: Promise<{reportId: string}>},
) {
  const {reportId} = await params;
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/reports/${reportId}`),
  );
}
