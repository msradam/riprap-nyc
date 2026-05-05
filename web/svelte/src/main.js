// Side-effect imports register the custom elements; agent.html mounts
// the same <r-briefing>, <r-trace>, <r-sources-footer> tags it always
// did — only the implementation changed.
import "./lib/SourcesFooter.svelte";
import "./lib/Briefing.svelte";
import "./lib/Trace.svelte";

// Re-export shared stores so non-Svelte code (legacy agent.js, the
// briefing chip-binding subscriber) can reach them. agent.js does:
//   import("/static/dist/riprap.js").then(m => m.highlightedDocId.set(id))
export { highlightedDocId, citeIndex } from "./lib/stores.js";
