import type {ReactNode} from 'react';
import {redirect} from 'next/navigation';
import {ProductShell} from '@/components/layout/product-shell';
import {hasSessionCookie} from '@/lib/server/service-session';

export default async function WorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
  if (!(await hasSessionCookie())) {
    redirect('/login');
  }

  return <ProductShell>{children}</ProductShell>;
}
