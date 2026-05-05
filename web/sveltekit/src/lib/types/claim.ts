import type { Tier } from './tier';

export interface Citation {
  id: string;
  n: number;
  tier: Tier;
  source: string;
  title: string;
  docId: string;
  url: string;
  vintage: string;
  retrieved: string;
}

export interface ClaimPart {
  text: string;
  tier?: Tier;
  cite?: string;
}

export type BriefingBlock =
  | { kind: 'status'; html: string }
  | { kind: 'head'; n: string; label: string; tier?: Tier; title?: string }
  | { kind: 'prose'; parts: ClaimPart[] };
