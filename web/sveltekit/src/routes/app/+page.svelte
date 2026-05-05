<script lang="ts">
  /** Cold-start state at /app — the "I'm ready to query" page.
   *
   *  Separated from the marketing landing at / per V0.4.5 README
   *  §"Landing page". The landing pulls a curious visitor in with a
   *  hero, a "what you'll get back" preview, and the five-Stones
   *  strip; the cold-start is what an analyst lands on once they
   *  click through to do work. */
  import ColdStart from '$lib/components/shell/ColdStart.svelte';
</script>

<section class="hero-band">
  <div class="hero-band-inner">
    <ColdStart />
  </div>
</section>
