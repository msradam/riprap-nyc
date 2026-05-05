<script lang="ts">
  import type { BriefingBlock, Citation } from '$lib/types/claim';
  import Claim from './Claim.svelte';
  import Cite from './Cite.svelte';
  import SectionHead from './SectionHead.svelte';

  interface Props {
    blocks: BriefingBlock[];
    citations: Record<string, Citation>;
    streaming?: boolean;
    replayKey?: number;
  }

  let { blocks, citations: cites, streaming = false, replayKey = 0 }: Props = $props();

  let visibleCount = $state(blocks.length);
  let prefersReducedMotion = $state(false);

  $effect(() => {
    if (typeof window === 'undefined') return;
    prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  $effect(() => {
    // re-run when replayKey changes
    void replayKey;
    if (!streaming) {
      visibleCount = blocks.length;
      return;
    }
    if (prefersReducedMotion) {
      visibleCount = blocks.length;
      return;
    }
    visibleCount = 0;
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      i++;
      visibleCount = i;
      if (i < blocks.length) {
        timer = setTimeout(tick, i < 2 ? 280 : 420);
      }
    };
    timer = setTimeout(tick, 240);
    return () => clearTimeout(timer);
  });
</script>

<div
  class="briefing-prose"
  role="log"
  aria-live="polite"
  aria-atomic="false"
  aria-label="Streaming flood-exposure briefing"
>
  {#each blocks.slice(0, visibleCount) as block, i (i)}
    {#if block.kind === 'status'}
      <!-- briefing-status HTML comes from either:
           (a) the static sample fixture (lib/data/sample.ts, trusted), or
           (b) the parser's preamble fallback (currently disabled).
           No user-supplied input flows here.
        -->
      <!-- eslint-disable-next-line svelte/no-at-html-tags -->
      <div class="briefing-status">{@html block.html}</div>
    {:else if block.kind === 'head'}
      <SectionHead n={block.n} label={block.label} tier={block.tier} title={block.title} />
    {:else}
      <p class="briefing-para">
        {#each block.parts as part, j (j)}
          {#if part.tier}
            <Claim tier={part.tier}>{part.text}</Claim>{#if part.cite && cites[part.cite]}<Cite c={cites[part.cite]} />{/if}
          {:else}
            <span>{part.text}</span>
          {/if}
        {/each}
      </p>
    {/if}
  {/each}
  {#if visibleCount < blocks.length}
    <span class="streaming-caret" aria-hidden="true">▍</span>
  {/if}
</div>
