<script lang="ts">
  /** StandardsStrip — compliance badges.
   *
   *  Surfaces the civic-tech compliance registers the design and
   *  implementation satisfy. Aspirational badges (USWDS, WCAG 2.2 AA,
   *  Section 508, Plain Writing Act, OSS) serve as a procurement/audit
   *  shorthand for federal + state buyers. Drop badges that no longer
   *  hold; don't add badges the implementation can't substantiate.
   */
</script>

<div class="standards-strip" role="region" aria-label="Compliance badges">
  <span class="badge"><span class="tick">✓</span> <strong>USWDS</strong></span>
  <span class="badge"><span class="tick">✓</span> <strong>WCAG 2.2 AA</strong></span>
  <span class="badge"><span class="tick">✓</span> <strong>Section 508</strong></span>
  <span class="badge"><span class="tick">✓</span> <strong>Plain Writing Act</strong></span>
  <span class="badge"><span class="tick">✓</span> <strong>Open source</strong>&nbsp;· Apache-2.0</span>
</div>

<style>
  .standards-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 28px;
    padding-top: 18px;
    border-top: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--ink-tertiary);
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px 4px 0;
    margin-right: 14px;
    border-right: 1px solid var(--rule-soft);
    color: var(--ink-secondary);
  }
  .badge:last-child {
    border-right: none;
    margin-right: 0;
  }
  .badge .tick {
    color: var(--accent);
    font-weight: 600;
  }
  .badge strong {
    color: var(--ink);
    font-family: var(--font-sans);
    font-weight: 600;
    letter-spacing: 0.02em;
  }
</style>
