import type {ReportSection, SectionPlanningContext} from '@/lib/api/types';

export type SectionTreeNode = ReportSection & {children: SectionTreeNode[]};

export function buildSectionTree(sections: ReportSection[]): SectionTreeNode[] {
  const byId = new Map<string, SectionTreeNode>();
  for (const section of sections) {
    byId.set(section.id, {...section, children: []});
  }

  const roots: SectionTreeNode[] = [];
  for (const section of sections) {
    const node = byId.get(section.id)!;
    if (section.parent_id && section.parent_id !== section.id) {
      const parent = byId.get(section.parent_id);
      if (parent) {
        parent.children.push(node);
        continue;
      }
    }
    roots.push(node);
  }

  const sortNodes = (nodes: SectionTreeNode[]) => {
    nodes.sort(
      (left, right) =>
        left.sort_order - right.sort_order ||
        left.title.localeCompare(right.title),
    );
    for (const node of nodes) sortNodes(node.children);
  };
  sortNodes(roots);
  return roots;
}

export function countPlanningContext(context: SectionPlanningContext) {
  return {
    disclosures: context.disclosures.length,
    requirements: context.requirements.length,
    facts: context.facts.length,
    evidence: context.evidence.length,
    missing: context.missing_items.length,
  };
}

export function formatPlanningEvidenceLocator(
  evidence: SectionPlanningContext['evidence'][number],
) {
  if (evidence.sheet_name || evidence.cell_range) {
    return [
      evidence.sheet_name ? `Sheet: ${evidence.sheet_name}` : null,
      evidence.cell_range ? `Cell: ${evidence.cell_range}` : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  if (evidence.page_start != null) {
    return evidence.page_end != null &&
      evidence.page_end !== evidence.page_start
      ? `Pages ${evidence.page_start}–${evidence.page_end}`
      : `Page ${evidence.page_start}`;
  }
  if (evidence.slide_number != null) return `Slide ${evidence.slide_number}`;
  if (evidence.heading_path?.length) return evidence.heading_path.join(' › ');
  return evidence.anchor_type;
}
