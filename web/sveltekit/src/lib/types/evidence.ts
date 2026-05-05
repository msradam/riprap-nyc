import type { Tier } from './tier';

export type EvidenceFmt =
  | { kind: 'scalar'; value: string; unit: string; aux?: string }
  | { kind: 'table'; columns: string[]; rows: string[][] }
  | { kind: 'spark'; data: number[]; headline: string; sub: string }
  | { kind: 'histogram'; data: number[]; headline: string; sub: string }
  | {
      kind: 'forecast';
      data: Array<{ year: number; low: number; mid: number; high: number }>;
      caption?: string;
    }
  | { kind: 'thumb'; thumbKind: 'stormwater' | 'synthetic'; sub: string };

export interface EvidenceItem {
  id: string;
  citeId: string;
  tier: Tier;
  source: string;
  title: string;
  docId: string;
  vintage: string;
  fmt: EvidenceFmt;
}
