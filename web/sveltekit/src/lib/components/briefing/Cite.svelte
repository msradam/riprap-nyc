<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import { citations } from '$lib/stores/citations.svelte';

  interface Props { c: Citation; }
  let { c }: Props = $props();

  function activate(e: MouseEvent) {
    e.preventDefault();
    citations.active = c.id;
    const el = document.getElementById(`cite-${c.id}`);
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
</script>

<a
  href="#cite-{c.id}"
  class="inline-cite"
  data-cite={c.id}
  onclick={activate}
  aria-label="Citation {c.n}: {c.source}, {c.title}"
><sup>[{c.n}]</sup></a>
