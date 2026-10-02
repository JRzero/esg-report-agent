import type {DocumentSourceType} from '@/lib/api/types';

export const materialSourcePolicy: Record<
  DocumentSourceType,
  {
    label: string;
    description: string;
    badge: 'teal' | 'purple' | 'blue' | 'neutral';
    mayExtractFacts: boolean;
  }
> = {
  EVIDENCE: {
    label: 'Evidence',
    description: '企业当前项目的原始材料，可用于支撑 Fact。',
    badge: 'teal',
    mayExtractFacts: true,
  },
  REFERENCE: {
    label: 'Reference',
    description: '仅用于结构、表达和行业参考，不得作为当前企业事实证据。',
    badge: 'purple',
    mayExtractFacts: false,
  },
  STANDARD: {
    label: 'Standard',
    description: '报告准则与披露规则，不代表企业自身事实。',
    badge: 'blue',
    mayExtractFacts: false,
  },
  HISTORICAL: {
    label: 'Historical',
    description: '历史期间材料，可提取候选事实，但必须保留期间并重新确认。',
    badge: 'neutral',
    mayExtractFacts: true,
  },
};

export function canExtractFacts(sourceType: DocumentSourceType) {
  return materialSourcePolicy[sourceType].mayExtractFacts;
}
