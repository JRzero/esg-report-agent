export type DocumentSourceType =
  | 'EVIDENCE'
  | 'REFERENCE'
  | 'STANDARD'
  | 'HISTORICAL';

export type FactStatus = 'PENDING' | 'CONFIRMED' | 'CONFLICT' | 'REJECTED';

export type CoverageStatus = 'MISSING' | 'PARTIAL' | 'COVERED';

export type MissingItemStatus =
  | 'MISSING'
  | 'REQUESTED'
  | 'RECEIVED'
  | 'RESOLVED'
  | 'NOT_APPLICABLE';

export type MissingItemPriority = 'LOW' | 'MEDIUM' | 'HIGH';
