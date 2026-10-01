import Link from 'next/link';
import type {ReactNode} from 'react';
import {ProjectWorkspaceNav} from '@/components/projects/project-workspace-nav';

export default async function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-4">
        <Link className="text-sm opacity-60 hover:opacity-100" href="/projects">
          ← 返回项目
        </Link>
      </div>
      <ProjectWorkspaceNav projectId={projectId} />
      <div className="pt-6">{children}</div>
    </div>
  );
}
