<script lang="ts">
  import type { TraceNode } from '$lib/types/trace';
  import TraceRow from './TraceRow.svelte';

  interface Props { root: TraceNode; }
  let { root }: Props = $props();

  let collapsed = $state(false);

  // Walk the tree to gather leaf specialist nodes — anything that isn't
  // a structural grouping (fan / merge). This handles the TTM parent
  // node introduced for foundation-model grouping: its three TTM
  // children still count toward fired/silent/errors.
  function collectLeaves(n: TraceNode, out: TraceNode[]): void {
    if (n.status === 'fan' || n.status === 'merge') {
      for (const c of n.children ?? []) collectLeaves(c, out);
      return;
    }
    out.push(n);
    for (const c of n.children ?? []) collectLeaves(c, out);
  }
  let leafSteps = $derived.by(() => {
    const acc: TraceNode[] = [];
    for (const c of root.children ?? []) collectLeaves(c, acc);
    return acc;
  });
  let totalMs = $derived(
    root.ms > 0 ? root.ms : leafSteps.reduce((s, n) => s + (n.ms || 0), 0)
  );
  let totalSecs = $derived((totalMs / 1000).toFixed(2));
  let fired = $derived(leafSteps.filter((n) => n.status === 'ok').length);
  let silent = $derived(leafSteps.filter((n) => n.status === 'silent').length);
  let errors = $derived(leafSteps.filter((n) => n.status === 'error').length);
</script>

<section class="trace-ui" class:is-collapsed={collapsed} aria-label="Run trace">
  <header class="trace-head">
    <div class="trace-head-left">
      <span class="section-label">Run trace</span>
      <span class="trace-head-meta">
        <span class="trace-head-stat">{totalSecs}s total</span>
        <span class="trace-head-sep">·</span>
        <span class="trace-head-stat">{fired} fired</span>
        <span class="trace-head-sep">·</span>
        <span class="trace-head-stat trace-head-silent">{silent} silent</span>
        <span class="trace-head-sep">·</span>
        <span class="trace-head-stat">{errors} errors</span>
      </span>
    </div>
    <button
      type="button"
      class="trace-collapse-btn"
      onclick={() => (collapsed = !collapsed)}
      aria-expanded={!collapsed}
    >
      {collapsed ? 'Expand ▾' : 'Collapse ▴'}
    </button>
  </header>
  {#if !collapsed}
    <div class="trace-body">
      <div class="trace-col-heads">
        <span></span><span></span>
        <span class="trace-col-head">action</span>
        <span class="trace-col-head">elapsed</span>
        <span class="trace-col-head">tier</span>
      </div>
      <div class="trace-tree" role="tree">
        <TraceRow node={root} defaultOpen={true} />
      </div>
    </div>
  {/if}
</section>
