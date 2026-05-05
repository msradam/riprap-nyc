// Shared state across all three custom elements. Svelte stores have
// .subscribe (Svelte runtime uses it) AND a manual subscribe is exposed
// here so legacy agent.js can wire vanilla DOM to the same signal that
// Svelte components react to.
import { writable } from "svelte/store";

export const highlightedDocId = writable(null);
// { doc_id: number } — Briefing populates as it encounters citations,
// SourcesFooter renders the numbered list from this.
export const citeIndex = writable({});
