<script lang="ts">
  /**
   * Riprap dam mark.
   * Source: "Dam" by Chintuza via the Noun Project (CC-BY 3.0).
   * The original SVG had embedded "Created by Chintuza / from the
   * Noun Project" text; that attribution has been stripped from the
   * artwork and is now carried in body copy (see AppFooter +
   * README + slides/deck.md).
   *
   * Inline SVG so it inherits `currentColor` from the surrounding
   * element — federal blue on light surfaces, paper on dark. No
   * extra HTTP request, sharp at any DPI.
   */
  interface Props {
    /** Pixel size of the square mark. Default 18px (wordmark scale). */
    size?: number;
    /** Aria label override; default 'Riprap'. */
    label?: string;
  }
  let { size = 18, label = 'Riprap' }: Props = $props();
</script>

<svg
  class="rip-mark"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 36 36"
  width={size}
  height={size}
  fill="currentColor"
  role="img"
  aria-label={label}
>
  <rect x="2.16669" y="3" width="9.99998" height="3.33333" />
  <rect x="2.16669" y="9.66665" width="9.99998" height="3.33333" />
  <rect x="2.16669" y="16.3333" width="9.99998" height="3.3334" />
  <rect x="2.16669" y="23.00002" width="9.99998" height="3.33333" />
  <rect x="2.16669" y="29.66667" width="9.99998" height="3.33333" />
  <rect x="23.83334" y="23.00002" width="9.99998" height="3.33333" />
  <rect x="23.83334" y="29.66667" width="9.99998" height="3.33333" />
  <path d="M13.83336,3V33h8.33335V11.33335A8.33337,8.33337,0,0,0,13.83336,3Z" />
</svg>

<style>
  .rip-mark {
    display: inline-block;
    flex-shrink: 0;
    /* Subtle visual alignment with adjacent baseline-set text. */
    transform: translateY(2px);
    color: var(--accent);
  }
</style>
