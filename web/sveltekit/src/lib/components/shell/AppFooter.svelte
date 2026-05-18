<script lang="ts">
  import { deployment } from '$lib/stores/deployment.svelte';
  // NYC-only "for residents, see…" resource links. Only render when
  // the active deployment is NYC — under a Boston / Chicago / SF /
  // Seattle / out-of-coverage chip these resources would be either
  // out of scope (FloodHelpNY is a NY-state nonprofit) or
  // misdirection (FloodNet NYC has no Boston coverage).
  let showNycResources = $derived(deployment.current?.name === 'nyc');
</script>

<footer class="app-footer no-print">
  <div class="app-footer-inner">
    <p class="app-footer-guard">
      <strong>Riprap is a reference dossier, not a stamped engineering memo, risk score, or disclosure.</strong>
      It is informational only; not a substitute for a licensed professional, and
      not designed for personal property decisions, real-estate transactions, or
      mortgage / insurance underwriting.{#if showNycResources}
        For residents, see
        <!-- nyc-leak-ok: links gated on showNycResources (deployment === 'nyc') -->
        <a href="https://www.floodhelpny.org">FloodHelpNY</a>
        <!-- nyc-leak-ok: same gate as the FloodHelpNY link above -->
        · <a href="https://www.floodnet.nyc">FloodNet NYC</a>.{/if}
    </p>
    <p class="app-footer-build">
      All foundation models Apache-2.0 · All data from public-record federal, state, and city sources · No commercial APIs contacted at runtime · Riprap v0.5.0 · build 2026-05-07
    </p>
    <p class="app-footer-credits">
      Dam mark: <a href="https://thenounproject.com/icon/dam-4516918/">"Dam" by Chintuza</a> via the Noun Project, CC-BY 3.0.
    </p>
  </div>
</footer>
