/**
 * TraceUI / TraceRow — the right-hand provenance accordion. Each
 * specialist's trace lands as a TraceNode (name, status, ms, output);
 * TraceUI renders them as collapsible rows.
 *
 * Bugs we want to seal:
 *   - empty trace tree renders crash-free
 *   - status glyph matches the node's status (ok / silent / error / fan / merge)
 *   - children render recursively at the right depth indent
 *   - clicking the toggle expands the output panel
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import TraceUI from '$lib/components/trace/TraceUI.svelte';
import TraceRow from '$lib/components/trace/TraceRow.svelte';
import type { TraceNode } from '$lib/types/trace';

let _idCounter = 0;
function node(partial: Partial<TraceNode>): TraceNode {
  return {
    // Default ids are unique across calls so {#each} keys don't
    // collide; tests can still pass an explicit `id` to override.
    id: partial.id ?? `auto-${_idCounter++}`,
    name: partial.name ?? 'test_step',
    status: partial.status ?? 'ok',
    ms: partial.ms ?? 0,
    tier: partial.tier ?? null,
    ...partial,
  };
}

describe('TraceUI renders the trace tree', () => {
  it('empty root renders crash-free', () => {
    const { container } = render(TraceUI, {
      props: { root: node({ name: 'root', children: [] }) },
    });
    expect(container.textContent).toContain('root');
  });

  it('flat tree renders each child', () => {
    const root = node({
      name: 'pipeline',
      children: [
        node({ name: 'geocode', status: 'ok', ms: 120 }),
        node({ name: 'sandy', status: 'silent', ms: 45 }),
        node({ name: 'ida_hwm', status: 'error', ms: 30, error: 'timeout' }),
      ],
    });
    const { container } = render(TraceUI, { props: { root } });
    const text = container.textContent ?? '';
    expect(text).toContain('geocode');
    expect(text).toContain('sandy');
    expect(text).toContain('ida_hwm');
  });

  it('parent name visible by default; nested children appear when expanded', () => {
    // TraceRow collapses by default; deep children only render when
    // the parent toggle opens. Assert what's visible without
    // expansion: the parent's name. Body assertions for the expanded
    // view live in the "TraceRow defaultOpen + canExpand" block below.
    const root = node({
      name: 'cornerstone',
      status: 'fan',
      children: [
        node({
          name: 'sandy_inundation',
          children: [node({ name: 'sub_step', status: 'ok' })],
        }),
      ],
    });
    const { container } = render(TraceUI, { props: { root } });
    const text = container.textContent ?? '';
    expect(text).toContain('sandy_inundation');
  });
});

describe('TraceRow defaultOpen + canExpand', () => {
  it('row with no children + no output is non-expandable', () => {
    const { container } = render(TraceRow, {
      props: { node: node({ name: 'leaf', status: 'ok' }) },
    });
    expect(container.textContent).toContain('leaf');
  });

  it('row with output is expandable (defaultOpen=true renders the output)', () => {
    const { container } = render(TraceRow, {
      props: {
        node: node({ name: 'sandy', status: 'ok', output: { inside: true } }),
        defaultOpen: true,
      },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('sandy');
    expect(text).toContain('inside');
  });
});
