'use client';

import type {ReactNode} from 'react';
import {usePathname} from 'next/navigation';
import {AppShell} from '@astryxdesign/core/AppShell';
import {SideNav, SideNavItem, SideNavSection} from '@astryxdesign/core/SideNav';

const navigation = [
  {label: '概览', href: '/'},
  {label: '项目', href: '/projects'},
  {label: '资料', href: '/materials'},
  {label: '事实', href: '/facts'},
  {label: 'GRI', href: '/gri'},
  {label: '报告', href: '/reports'},
];

export function ProductShell({children}: {children: ReactNode}) {
  const pathname = usePathname();

  return (
    <AppShell
      height="fill"
      variant="section"
      contentPadding={0}
      mobileNav={{breakpoint: 'md'}}
      sideNav={
        <SideNav
          collapsible={{buttonLabel: '折叠导航'}}
          resizable={{defaultWidth: 256, minWidth: 220, maxWidth: 360, autoSaveId: 'esg-main-nav'}}
          header={
            <div className="px-4 py-3">
              <div className="text-sm font-semibold">ESG Report Agent</div>
              <div className="mt-1 text-xs opacity-60">Evidence-first workspace</div>
            </div>
          }>
          <SideNavSection title="工作台">
            {navigation.map((item) => (
              <SideNavItem
                key={item.href}
                label={item.label}
                href={item.href}
                isSelected={pathname === item.href}
              />
            ))}
          </SideNavSection>
        </SideNav>
      }>
      {children}
    </AppShell>
  );
}
