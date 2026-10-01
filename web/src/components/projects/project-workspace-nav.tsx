'use client';

import {usePathname} from 'next/navigation';
import {Tab, TabList} from '@astryxdesign/core/TabList';

const sections = [
  {key: 'overview', label: '概览', segment: ''},
  {key: 'materials', label: '资料', segment: 'materials'},
  {key: 'facts', label: '事实', segment: 'facts'},
  {key: 'reports', label: '报告', segment: 'reports'},
  {key: 'gri', label: 'GRI', segment: 'gri'},
  {key: 'missing', label: '缺失资料', segment: 'missing'},
  {key: 'members', label: '成员', segment: 'members'},
];

export function ProjectWorkspaceNav({projectId}: {projectId: string}) {
  const pathname = usePathname();
  const selected =
    sections.find((section) => {
      const href = section.segment
        ? `/projects/${projectId}/${section.segment}`
        : `/projects/${projectId}`;
      return pathname === href;
    })?.key ?? 'overview';

  return (
    <TabList
      value={selected}
      onChange={() => undefined}
      size="sm"
      hasDivider>
      {sections.map((section) => {
        const href = section.segment
          ? `/projects/${projectId}/${section.segment}`
          : `/projects/${projectId}`;
        return (
          <Tab
            key={section.key}
            value={section.key}
            label={section.label}
            href={href}
          />
        );
      })}
    </TabList>
  );
}
