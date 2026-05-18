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

  // svelte-ignore state_referenced_locally — `blocks.length` is read
  // once for the initial value; the $effect below keeps visibleCount
  // synced after that (either by snapping to full count when not
  // streaming, or by stepping through during animated reveal).
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
      <!-- briefing-status HTML comes from the parser's preamble
           fallback (currently disabled). No user-supplied input flows
           through this @html sink.
        -->
      <!-- eslint-disable-next-line svelte/no-at-html-tags -->
      <div class="briefing-status briefing-fade-in">{@html block.html}</div>
    {:else if block.kind === 'head'}
      <div class="briefing-fade-in">
        <SectionHead n={block.n} label={block.label} tier={block.tier} title={block.title} />
      </div>
    {:else}
      <p class="briefing-para briefing-fade-in">
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
</div>

<style>
  /* Each newly-revealed block fades in over 320ms instead of the
     blinking-cursor "typing" cadence. Citation-grounded paragraphs
     should land with authority, not chatter. Respects
     prefers-reduced-motion via the global rule in tokens.css. */
  .briefing-fade-in {
    animation: briefing-fade 320ms ease-out both;
  }
  @keyframes briefing-fade {
    from { opacity: 0; transform: translateY(2px); }
    to   { opacity: 1; transform: translateY(0); }
  }
</style>
