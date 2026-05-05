/** Cross-component highlight state — Svelte 5 rune-based store. */
class CitationState {
  active = $state<string | null>(null);
  highlightDocId = $state<string | null>(null);
}

export const citations = new CitationState();
