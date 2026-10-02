import type {
  MissingItemStatus,
  ProjectDisclosure,
  ProjectDisclosureCoverage,
  ProjectRequirement,
} from '@/lib/api/types';

export type EffectiveDisclosureStatus =
  | ProjectDisclosureCoverage
  | 'NOT_APPLICABLE';

export function effectiveDisclosureStatus(
  disclosure: ProjectDisclosure,
): EffectiveDisclosureStatus {
  return disclosure.applicability === 'NOT_APPLICABLE'
    ? 'NOT_APPLICABLE'
    : disclosure.coverage_status;
}

export function disclosureStatusLabel(status: EffectiveDisclosureStatus) {
  return {
    COVERED: '已覆盖',
    PARTIAL: '部分覆盖',
    MISSING: '缺失',
    NOT_APPLICABLE: '不适用',
  }[status];
}

export function disclosureStatusVariant(
  status: EffectiveDisclosureStatus,
): 'green' | 'warning' | 'error' | 'neutral' {
  switch (status) {
    case 'COVERED':
      return 'green';
    case 'PARTIAL':
      return 'warning';
    case 'MISSING':
      return 'error';
    case 'NOT_APPLICABLE':
      return 'neutral';
  }
}

export function countDisclosureStatuses(disclosures: ProjectDisclosure[]) {
  const counts: Record<EffectiveDisclosureStatus | 'TOTAL', number> = {
    TOTAL: disclosures.length,
    COVERED: 0,
    PARTIAL: 0,
    MISSING: 0,
    NOT_APPLICABLE: 0,
  };
  for (const disclosure of disclosures) {
    counts[effectiveDisclosureStatus(disclosure)] += 1;
  }
  return counts;
}

export function requirementMetricCodes(
  requirement: Pick<ProjectRequirement, 'required_data_json'>,
): string[] {
  const value = requirement.required_data_json.metric_codes;
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

export const missingItemStatusLabel: Record<MissingItemStatus, string> = {
  MISSING: '待补充',
  REQUESTED: '已请求',
  RECEIVED: '已收到',
  RESOLVED: '已解决',
  NOT_APPLICABLE: '不适用',
};
