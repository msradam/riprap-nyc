<script lang="ts">
  import * as YAML from 'js-yaml';

  import {
    parseFile,
    generateManifest,
    type ParsedFile,
    type PebbleMapping,
    type StoneKey,
    type Tier,
  } from '$lib/client/byod';
  import { byodRegistry } from '$lib/stores/byodRegistry.svelte';

  /** BYOD modal — three-section workflow:
   *
   *    §1 File     — drop / click-to-choose. Files stay in browser.
   *    §2 Adapter  — auto-detect from extension + header sniff. User
   *                  can override.
   *    §3 Pebble   — name + stone + tier + radius. Live manifest YAML
   *                  preview.
   *
   *  On commit, the parsed payload + generated manifest are persisted
   *  to IndexedDB via the byodRegistry store. Cross-session sharing
   *  + server-side merge into a live briefing run are deferred.
   */

  interface Props {
    open: boolean;
    onClose: () => void;
  }
  let { open, onClose }: Props = $props();

  let dragOver = $state(false);
  let parsed = $state<ParsedFile | null>(null);
  let parseError = $state<string | null>(null);
  let parsing = $state(false);

  // §3 — pebble mapping fields (the user can override the auto-detected
  // adapter via a separate radio; see selectedAdapter state).
  let mapping = $state<PebbleMapping>({
    pebbleName: '',
    title: '',
    stone: 'keystone',
    tier: 'empirical',
    radiusM: 800,
  });

  /** Snake-case slug for an arbitrary filename — used to suggest a
   *  default pebble id. Lowercase, alnum + underscores, stripped
   *  extension. */
  function slugify(name: string): string {
    return name
      .replace(/\.[^.]+$/, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 40);
  }

  async function handleFile(file: File) {
    parsing = true;
    parseError = null;
    parsed = null;
    try {
      const p = await parseFile(file);
      parsed = p;
      // Pre-fill the mapping with sensible defaults
      mapping.pebbleName = slugify(file.name);
      mapping.title = file.name.replace(/\.[^.]+$/, '');
      // Stone defaults by adapter kind
      if (p.detected === 'geojson_polygons') {
        mapping.stone = 'cornerstone';
        mapping.tier = 'modeled';
      } else if (p.detected === 'socrata_records') {
        mapping.stone = 'touchstone';
        mapping.tier = 'empirical';
      }
    } catch (e: unknown) {
      parseError = e instanceof Error ? e.message : String(e);
    } finally {
      parsing = false;
    }
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    dragOver = true;
  }
  function onDragLeave() { dragOver = false; }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    const f = e.dataTransfer?.files?.[0];
    if (f) void handleFile(f);
  }
  function onChooseClick() {
    const inp = document.getElementById('byod-file-input') as HTMLInputElement | null;
    inp?.click();
  }
  function onFileChange(e: Event) {
    const t = e.target as HTMLInputElement;
    const f = t.files?.[0];
    if (f) void handleFile(f);
  }

  /** Live-preview manifest YAML. Updates as mapping fields change. */
  let manifestPreview = $derived.by(() => {
    if (!parsed) return '';
    const obj = generateManifest(parsed, mapping);
    try {
      return YAML.dump(obj, { noRefs: true, lineWidth: 80 });
    } catch (e) {
      return `# preview failed: ${String(e)}`;
    }
  });

  async function commitPebble() {
    if (!parsed) return;
    const manifest = generateManifest(parsed, mapping);
    await byodRegistry.add(manifest, parsed.raw);
    onClose();
  }

  function reset() {
    parsed = null;
    parseError = null;
    mapping = {
      pebbleName: '',
      title: '',
      stone: 'keystone',
      tier: 'empirical',
      radiusM: 800,
    };
  }

  const STONES: { id: StoneKey; label: string }[] = [
    { id: 'cornerstone', label: 'Cornerstone (the hazard ground)' },
    { id: 'keystone',    label: 'Keystone (the asset register)' },
    { id: 'touchstone',  label: 'Touchstone (live observation)' },
    { id: 'lodestone',   label: 'Lodestone (projection)' },
    { id: 'capstone',    label: 'Capstone (synthesis)' },
  ];
  const TIERS: { id: Tier; label: string }[] = [
    { id: 'empirical', label: 'Empirical' },
    { id: 'modeled',   label: 'Modeled' },
    { id: 'proxy',     label: 'Proxy' },
    { id: 'synthetic', label: 'Synthetic' },
  ];
</script>

{#if open}
  <div
    class="byod-overlay"
    role="presentation"
    onclick={onClose}
    onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
  ></div>
  <div
    class="byod-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="byod-title"
  >
    <header class="byod-head">
      <h2 id="byod-title" class="byod-title">Bring your own data</h2>
      <button type="button" class="byod-close" aria-label="Close" onclick={onClose}>✕</button>
    </header>

    <p class="byod-intro">
      Files stay on your computer. The parsed manifest is stored in this
      browser's IndexedDB so it survives reloads, but nothing is uploaded.
      <a href="/docs/byod" target="_blank" rel="noopener">How BYOD works ↗</a>
    </p>

    <!-- §1 File -->
    <section class="byod-section">
      <span class="byod-step">1. File</span>
      {#if !parsed}
        <button
          type="button"
          class="byod-drop"
          class:is-dragover={dragOver}
          ondragover={onDragOver}
          ondragleave={onDragLeave}
          ondrop={onDrop}
          onclick={onChooseClick}
        >
          <span class="byod-drop-icon" aria-hidden="true">↓</span>
          <div class="byod-drop-text">
            <strong>Drop a file here</strong>
            <span>or click to choose</span>
          </div>
        </button>
        <input
          id="byod-file-input"
          type="file"
          accept=".csv,.json,.geojson,.yaml,.yml"
          style="display:none"
          onchange={onFileChange}
        />
        <p class="byod-supported">
          Supported: <code>.csv</code> · <code>.json</code> · <code>.geojson</code> · <code>.yaml</code> · <code>.yml</code>
        </p>
        {#if parseError}
          <p class="byod-error">{parseError}</p>
        {/if}
        {#if parsing}
          <p class="byod-status">Parsing…</p>
        {/if}
      {:else}
        <div class="byod-loaded">
          <strong>{parsed.filename}</strong>
          <span>· {parsed.rowCount.toLocaleString()} records · {(parsed.size / 1024).toFixed(1)} KB</span>
          <button type="button" class="byod-relink" onclick={reset}>Choose a different file</button>
        </div>
      {/if}
    </section>

    {#if parsed}
      <!-- §2 Adapter -->
      <section class="byod-section">
        <span class="byod-step">2. Adapter</span>
        <div class="byod-detected">
          <strong>{parsed.detected.replace(/_/g, ' ')}</strong>
          <span class="byod-detected-reason">{parsed.reason}</span>
        </div>
      </section>

      <!-- §3 Pebble mapping -->
      <section class="byod-section">
        <span class="byod-step">3. Pebble mapping</span>
        <div class="byod-fields">
          <label class="byod-field">
            <span class="byod-label">Pebble name</span>
            <input
              type="text"
              bind:value={mapping.pebbleName}
              pattern="[a-z][a-z0-9_]*"
              required
              placeholder="my_properties"
            />
            <span class="byod-hint">snake_case, starts with a letter — used as the manifest <code>id</code></span>
          </label>

          <label class="byod-field">
            <span class="byod-label">Card title</span>
            <input
              type="text"
              bind:value={mapping.title}
              placeholder="Owned properties near this address"
            />
          </label>

          <label class="byod-field">
            <span class="byod-label">Stone</span>
            <select bind:value={mapping.stone}>
              {#each STONES as s (s.id)}
                <option value={s.id}>{s.label}</option>
              {/each}
            </select>
          </label>

          <label class="byod-field">
            <span class="byod-label">Tier</span>
            <select bind:value={mapping.tier}>
              {#each TIERS as t (t.id)}
                <option value={t.id}>{t.label}</option>
              {/each}
            </select>
          </label>

          {#if parsed.detected === 'socrata_records' || parsed.detected === 'csv_records'}
            <label class="byod-field">
              <span class="byod-label">Search radius (m)</span>
              <input
                type="number"
                bind:value={mapping.radiusM}
                min="50"
                max="10000"
                step="50"
              />
            </label>
          {/if}
        </div>

        <details class="byod-preview">
          <summary>Manifest preview (YAML)</summary>
          <pre>{manifestPreview}</pre>
        </details>
      </section>

      <footer class="byod-foot">
        <button type="button" class="byod-cancel" onclick={onClose}>Cancel</button>
        <button
          type="button"
          class="byod-commit"
          onclick={commitPebble}
          disabled={!mapping.pebbleName || !mapping.title}
        >Save pebble</button>
      </footer>
    {/if}
  </div>
{/if}

<style>
  .byod-overlay {
    position: fixed; inset: 0;
    background: rgba(15, 23, 42, 0.45);
    z-index: 998;
  }
  .byod-dialog {
    position: fixed;
    inset: 5vh auto auto 50%;
    transform: translateX(-50%);
    width: min(720px, 92vw);
    max-height: 90vh;
    overflow: auto;
    background: var(--paper);
    border: 1px solid var(--ink);
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
    z-index: 999;
    padding: 24px 28px 22px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  .byod-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid var(--rule-soft);
    padding-bottom: 10px;
    margin-bottom: 14px;
  }
  .byod-title {
    margin: 0;
    font-family: var(--font-serif);
    font-size: 22px;
    font-weight: 500;
    letter-spacing: -0.01em;
  }
  .byod-close {
    background: transparent;
    border: 0;
    font-size: 18px;
    color: var(--ink-tertiary);
    cursor: pointer;
    padding: 4px 6px;
  }
  .byod-close:hover { color: var(--ink); }
  .byod-intro {
    font-size: 13px;
    color: var(--ink-secondary);
    margin: 0 0 18px;
    line-height: 1.5;
  }
  .byod-intro a { color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--accent); }

  .byod-section {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px dashed var(--rule-soft);
  }
  .byod-section:first-of-type {
    border-top: 0;
    padding-top: 0;
  }
  .byod-step {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-tertiary);
    margin-bottom: 8px;
  }
  .byod-drop {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 22px 18px;
    background: white;
    border: 1.5px dashed var(--rule-soft);
    cursor: pointer;
    transition: border-color 120ms ease, background-color 120ms ease;
    text-align: left;
  }
  .byod-drop:hover, .byod-drop.is-dragover {
    border-color: var(--accent);
    background: var(--reference-bg);
  }
  .byod-drop-icon {
    font-family: var(--font-mono);
    font-size: 22px;
    color: var(--accent);
    line-height: 1;
  }
  .byod-drop-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .byod-drop-text strong { font-size: 14px; color: var(--ink); }
  .byod-drop-text span { font-size: 12px; color: var(--ink-tertiary); }
  .byod-supported {
    margin: 10px 0 0;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
  .byod-supported code {
    background: var(--paper-deep);
    padding: 1px 5px;
    border: 1px solid var(--rule-soft);
    margin: 0 2px;
  }
  .byod-error {
    margin: 10px 0 0;
    font-size: 12px;
    color: var(--accent-alert);
  }
  .byod-status {
    margin: 10px 0 0;
    font-size: 12px;
    color: var(--ink-tertiary);
  }
  .byod-loaded {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 13px;
    background: white;
    border: 1px solid var(--rule-soft);
    padding: 8px 12px;
  }
  .byod-loaded strong { color: var(--ink); }
  .byod-loaded span { color: var(--ink-tertiary); }
  .byod-relink {
    margin-left: auto;
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 11px;
    padding: 3px 10px;
    cursor: pointer;
  }
  .byod-relink:hover { background: var(--accent); color: white; }

  .byod-detected strong {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--accent);
    text-transform: lowercase;
  }
  .byod-detected-reason {
    margin-left: 10px;
    font-size: 12px;
    color: var(--ink-secondary);
  }

  .byod-fields {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px 16px;
    margin-top: 8px;
  }
  .byod-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .byod-label {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--ink-secondary);
    text-transform: uppercase;
  }
  .byod-field input, .byod-field select {
    font-family: var(--font-sans);
    font-size: 13px;
    border: 1px solid var(--rule-soft);
    background: white;
    padding: 7px 10px;
    color: var(--ink);
  }
  .byod-field input:focus, .byod-field select:focus {
    outline: 3px solid var(--accent);
    outline-offset: 1px;
    border-color: var(--accent);
  }
  .byod-hint {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--ink-tertiary);
  }
  .byod-hint code {
    background: var(--paper-deep);
    padding: 0 4px;
    border: 1px solid var(--rule-soft);
  }

  .byod-preview {
    margin-top: 14px;
    border: 1px solid var(--rule-soft);
    background: white;
    padding: 10px 12px;
  }
  .byod-preview summary {
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-tertiary);
  }
  .byod-preview pre {
    font-family: var(--font-mono);
    font-size: 11.5px;
    line-height: 1.45;
    margin: 10px 0 0;
    padding: 10px 12px;
    background: var(--paper-deep);
    border: 1px solid var(--rule-soft);
    overflow: auto;
    color: var(--ink);
    max-height: 320px;
  }

  .byod-foot {
    margin-top: 18px;
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding-top: 14px;
    border-top: 1px solid var(--rule-soft);
  }
  .byod-cancel {
    background: transparent;
    border: 1px solid var(--rule-soft);
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 13px;
    color: var(--ink-secondary);
    padding: 8px 16px;
    cursor: pointer;
  }
  .byod-commit {
    background: var(--ink);
    color: var(--paper);
    border: 0;
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 13px;
    padding: 8px 18px;
    cursor: pointer;
    letter-spacing: 0.02em;
  }
  .byod-commit:hover { background: #000; }
  .byod-commit:disabled { background: var(--ink-tertiary); cursor: not-allowed; }

  @media (max-width: 640px) {
    .byod-fields { grid-template-columns: 1fr; }
  }
</style>
