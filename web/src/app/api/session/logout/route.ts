import {NextResponse} from 'next/server';
import {clearSessionTokens} from '@/lib/server/service-session';

export async function POST() {
  await clearSessionTokens();
  return NextResponse.json({authenticated: false});
}
