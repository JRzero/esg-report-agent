import {EmptyState} from '@astryxdesign/core/EmptyState';

const sectionCopy: Record<string, {title: string; description: string}> = {
  materials: {
    title: '资料中心将在下一阶段实现',
    description: '这里将承载 Evidence / Reference / Standard / Historical 上传、分类、版本和解析状态。',
  },
  facts: {
    title: 'Fact Center 尚未展开',
    description: '这里将承载 Fact 确认、Evidence 追溯、冲突处理和跨章节事实复用。',
  },
  reports: {
    title: '报告工作台尚未展开',
    description: '后续将实现左侧目录、中间 Block Editor、右侧 AI / Evidence / Fact。',
  },
  gri: {
    title: 'GRI 工作区尚未展开',
    description: '后续将实现 Disclosure / Requirement 覆盖状态和 Fact Mapping。',
  },
  missing: {
    title: '缺失资料工作区尚未展开',
    description: '后续将实现 Missing Item 请求、状态和资料补充闭环。',
  },
  members: {
    title: '项目成员管理尚未展开',
    description: '后续将连接 Project Member 与 OWNER / EDITOR / REVIEWER / CLIENT_MEMBER 权限。',
  },
};

export function ProjectSectionPlaceholder({section}: {section: string}) {
  const copy = sectionCopy[section] ?? {
    title: '模块尚未实现',
    description: '该项目模块将在后续 Spec 中实现。',
  };

  return (
    <div className="py-12">
      <EmptyState
        title={copy.title}
        description={copy.description}
        headingLevel={2}
      />
    </div>
  );
}

export function isKnownProjectSection(section: string) {
  return section in sectionCopy;
}
