// Shared reactive state for Riprap web components.
//
// Lit components import these signals; updating one signal re-renders
// every subscribed component. Replaces the hand-wired DOM-querying
// cross-linking we used to do in vanilla JS.

import { signal } from "https://esm.sh/@lit-labs/signals@0.1.x";

// Currently-highlighted citation doc_id. When a Briefing chip is hovered
// or clicked, this gets set; SourcesFooter observes it and highlights
// the matching row, and vice versa.
export const highlightedDocId = signal(null);

// The full agent run output (from /api/agent/stream `final` event).
// Components that need the result post-render read from this.
export const lastResult = signal(null);

// The cite-index map { doc_id: number } populated by Briefing as it
// renders the streamed markdown. SourcesFooter reads it to know which
// numbered rows to render.
export const citeIndex = signal({});
