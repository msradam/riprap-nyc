<svelte:options
  customElement={{
    tag: "r-trace",
    props: {
      stepLabels: { type: "Object" },
    },
  }} />

<script>
  import { onMount } from "svelte";
  import { fly, fade } from "svelte/transition";
  import { cubicOut } from "svelte/easing";

  let { stepLabels = {} } = $props();
  let steps = $state([]);

  // Imperative API consumed by legacy agent.js. Exposed via the host
  // element through onMount once the custom element is upgraded.
  onMount(() => {
    // `this` would be the wrapper context; rely on the component's
    // host element discovery via document.currentScript trickery is
    // brittle — Svelte exposes the host via the element instance.
    // We expose pushStep / clear via a custom event-driven API:
    //   el.dispatchEvent(new CustomEvent('riprap-trace-push', { detail: step }))
    //   el.dispatchEvent(new CustomEvent('riprap-trace-clear'))
    // But agent.js currently calls el.pushStep() / el.clear(); to keep
    // that ergonomic we attach methods to the host in onMount.
    // The host is the parent of the shadow root.
    const host = container?.getRootNode()?.host;
    if (host) {
      host.pushStep = (step) => { steps = [...steps, step]; };
      host.clear = () => { steps = []; };
    }
  });

  let container;

  const escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function classFor(step) {
    return step.ok === true ? "ok" : step.ok === false ? "err" : "running";
  }
  function markFor(step) {
    return step.ok === true ? "✓" : step.ok === false ? "✗" : "○";
  }
  function labelFor(step) {
    return (stepLabels[step.step] && stepLabels[step.step][0]) || step.step;
  }
  function hintFor(step) {
    return (stepLabels[step.step] && stepLabels[step.step][1]) || "";
  }
</script>

<ol bind:this={container} id="steps-list">
  {#each steps as step, i (i)}
    <li class={classFor(step)}
        in:fly={{ y: -8, duration: 220, easing: cubicOut }}>
      <span class="icon">{markFor(step)}</span>
      <div>
        <div class="label">{labelFor(step)}</div>
        <div class="meta">{hintFor(step)}</div>
      </div>
      {#if step.elapsed_s != null}
        <span class="time">{step.elapsed_s}s</span>
      {/if}
      {#if step.result}
        <div class="result">{JSON.stringify(step.result)}</div>
      {/if}
      {#if step.err}
        <div class="result" style="color:var(--nyc-scarlet, #b80000)">{step.err}</div>
      {/if}
    </li>
  {/each}
</ol>

<style>
  :host { display: block; }
  ol {
    list-style: none; margin: 0; padding: 4px 0;
    font-size: 12.5px;
  }
  li {
    display: grid;
    grid-template-columns: 18px 1fr auto;
    gap: 10px;
    padding: 7px 14px;
    border-bottom: 1px solid var(--line, #e5e7eb);
    align-items: baseline;
  }
  li:last-child { border-bottom: 0; }
  .icon { font-weight: 700; font-size: 14px; line-height: 1; }
  .running .icon { color: var(--nyc-blue, #1642DF); }
  .ok      .icon { color: var(--good, #1a8754); }
  .err     .icon { color: var(--nyc-scarlet, #b80000); }
  .label  { color: var(--text, #111); font-weight: 500; }
  .meta   { color: var(--text-muted, #6b7280); font-size: 11px; }
  .time   { font-family: var(--mono, monospace); color: var(--text-faint, #9ca3af); font-size: 11.5px; }
  .running { background: rgba(22, 66, 223, 0.04); }
  .result {
    grid-column: 2 / -1;
    color: var(--text-muted, #6b7280);
    font-size: 11px;
    font-family: var(--mono, monospace);
    margin-top: 3px;
    word-break: break-word;
    line-height: 1.4;
  }
</style>
