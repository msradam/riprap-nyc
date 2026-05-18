<script lang="ts">
  import type { TraceNode } from '$lib/types/trace';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
  import StatusGlyph from './StatusGlyph.svelte';
  import Self from './TraceRow.svelte';

  interface Props {
    node: TraceNode;
    depth?: number;
    defaultOpen?: boolean;
  }

  let { node, depth = 0, defaultOpen = false }: Props = $props();
  // svelte-ignore state_referenced_locally — `defaultOpen` is a
  // one-shot initial-value prop; once the row mounts, `open` is
  // user-controlled via the expand toggle.
  let open = $state(defaultOpen);
  let copied = $state(false);
  let hasChildren = $derived(!!node.children?.length);
  let hasOutput = $derived(node.output != null || !!node.error);
  let canExpand = $derived(hasChildren || hasOutput);
  let indent = $derived(depth * 16);

  function toggle() {
    if (canExpand) open = !open;
  }

  let outputIsObject = $derived(
    node.output != null && typeof node.output === 'object'
  );

  let formattedOutput = $derived.by(() => {
    if (node.error) return node.error;
    if (node.output == null) return '';
    if (typeof node.output === 'string') return node.output;
    try {
      return JSON.stringify(node.output, null, 2);
    } catch {
      return String(node.output);
    }
  });

  let outputLabel = $derived(
    node.status === 'error' ? 'Error'
      : node.status === 'silent' ? 'Silent reason'
      : 'Output'
  );

  async function copyOutput(ev: MouseEvent) {
    ev.stopPropagation();
    try {
      await navigator.clipboard.writeText(formattedOutput);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      /* ignore — older browser, no clipboard permission */
    }
  }
</script>

<div class="trace-row trace-row-{node.status}" style:padding-left="{indent + 12}px">
  <button
    type="button"
    class="trace-row-toggle"
    onclick={toggle}
    aria-expanded={canExpand ? open : undefined}
    aria-label="{node.name}, {node.ms}ms, {node.status}{node.note ? ', ' + node.note : ''}"
    disabled={!canExpand}
  >
    <span class="trace-tree-glyph" aria-hidden="true">
      {hasChildren ? (open ? '▾' : '▸') : (hasOutput ? (open ? '▾' : '▸') : '·')}
    </span>
    <span class="trace-status-col"><StatusGlyph status={node.status} /></span>
    <span class="trace-name-col">
      <span class="trace-name">{node.name}</span>
      {#if node.note}<span class="trace-note"> · {node.note}</span>{/if}
      {#if node.docId}<span class="trace-doc-id" title="cited in briefing as [{node.docId}]">[{node.docId}]</span>{/if}
    </span>
    <span class="trace-ms-col">{node.ms}ms</span>
    <span class="trace-tier-col">
      {#if node.tier}<TierBadge tier={node.tier} compact />{/if}
      {#if node.status === 'silent'}<span class="trace-silent-tag">silent</span>{/if}
    </span>
  </button>

  {#if open && hasOutput}
    <div class="trace-output-panel" style:margin-left="{indent + 44}px">
      <div class="trace-output-head">
        <span class="trace-output-label trace-output-label-{node.status}">{outputLabel}</span>
        {#if node.model}
          <span class="trace-output-model">model: <code>{node.model}</code></span>
        {/if}
        {#if node.claims != null}
          <span class="trace-output-claims-count">{node.claims} claim{node.claims === 1 ? '' : 's'} cited</span>
        {/if}
        {#if formattedOutput}
          <button
            type="button"
            class="trace-output-copy"
            onclick={copyOutput}
            aria-label="Copy {outputLabel.toLowerCase()} to clipboard"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        {/if}
      </div>
      {#if outputIsObject}
        <pre class="trace-output-pre">{formattedOutput}</pre>
      {:else}
        <p class="trace-output-text">{formattedOutput}</p>
      {/if}
    </div>
  {/if}
</div>
{#if open && hasChildren && node.children}
  {#each node.children as child (child.id)}
    <Self node={child} depth={depth + 1} defaultOpen={child.status === 'fan'} />
  {/each}
{/if}
