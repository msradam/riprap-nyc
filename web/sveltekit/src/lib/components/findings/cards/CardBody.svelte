<script lang="ts">
  import type { Card } from '$lib/types/card';
  import HeadlineBody from './HeadlineBody.svelte';
  import TabularBody from './TabularBody.svelte';
  import ScalarsBody from './ScalarsBody.svelte';
  import SparkBody from './SparkBody.svelte';
  import TimeseriesBody from './TimeseriesBody.svelte';
  import TimeseriesFtBody from './TimeseriesFtBody.svelte';
  import ForecastBody from './ForecastBody.svelte';
  import RasterBody from './RasterBody.svelte';
  import LulcBody from './LulcBody.svelte';
  import RegisterBody from './RegisterBody.svelte';
  import ComparisonBody from './ComparisonBody.svelte';
  import MetaBody from './MetaBody.svelte';

  /** Dispatcher: picks the body component for a card variant.
   *  Spark + histogram share SparkBody (same shape, different source field).
   *  Raster + raster-pred share RasterBody (synthetic chrome carries the
   *  illustrative tag + dashed top-rule from the parent FindingCard). */
  let { card }: { card: Card } = $props();
</script>

{#if card.variant === 'headline'}
  <HeadlineBody {card} />
{:else if card.variant === 'tabular'}
  <TabularBody {card} />
{:else if card.variant === 'scalars'}
  <ScalarsBody {card} />
{:else if card.variant === 'spark' || card.variant === 'histogram'}
  <SparkBody {card} />
{:else if card.variant === 'timeseries'}
  <TimeseriesBody {card} />
{:else if card.variant === 'timeseries-ft'}
  <TimeseriesFtBody {card} />
{:else if card.variant === 'forecast'}
  <ForecastBody {card} />
{:else if card.variant === 'raster' || card.variant === 'raster-pred'}
  <RasterBody {card} />
{:else if card.variant === 'lulc'}
  <LulcBody {card} />
{:else if card.variant === 'register'}
  <RegisterBody {card} />
{:else if card.variant === 'comparison'}
  <ComparisonBody {card} />
{:else if card.variant === 'meta'}
  <MetaBody {card} />
{:else}
  <div class="unknown">unknown variant: {card.variant}</div>
{/if}

<style>
  .unknown {
    padding: var(--s-3) var(--s-4);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
</style>
