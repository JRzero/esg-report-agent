import {
  forwardServiceResponse,
  serviceSessionFetch,
} from '@/lib/server/service-session';

export async function POST(
  request: Request,
  {params}: {params: Promise<{documentId: string}>},
) {
  const {documentId} = await params;
  const formData = await request.formData();
  return forwardServiceResponse(
    await serviceSessionFetch(`/api/v1/documents/${documentId}/versions`, {
      method: 'POST',
      body: formData,
    }),
  );
}
