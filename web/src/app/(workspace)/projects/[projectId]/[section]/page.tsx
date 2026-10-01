import {notFound} from 'next/navigation';
import {
  isKnownProjectSection,
  ProjectSectionPlaceholder,
} from '@/components/projects/project-section-placeholder';

export default async function ProjectSectionPage({
  params,
}: {
  params: Promise<{projectId: string; section: string}>;
}) {
  const {section} = await params;
  if (!isKnownProjectSection(section)) notFound();

  return <ProjectSectionPlaceholder section={section} />;
}
