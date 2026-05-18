/**
 * Active-deployment descriptor — fetched once on app load from
 * `/api/deployment`. Drives the header chip text, browser title, and
 * the city-name shown in the hero on app pages.
 *
 * Landing page intentionally renders the hazard-agnostic
 * "Climate-exposure briefing" chip regardless of the active deployment
 * — the city is implied by the cycling H1 + city picker, not the chip.
 * App pages use the active deployment's actual hazard + city.
 */

export interface Deployment {
  /** Directory name — `nyc`, `boston`, `chicago`, `heat`, `air`, ... */
  name: string;
  /** Display city — `NYC`, `Boston`, `Chicago`, ... */
  city: string;
  /** Hazard tagline — `Flood-exposure briefing`, `Heat-exposure briefing`, ... */
  hazard: string;
}

class DeploymentStore {
  current = $state<Deployment | null>(null);
  loaded = $state(false);
  error = $state<string | null>(null);
  /** True once setForQuery() has been called for THIS query. Prevents
   *  a slow boot-time load() from overwriting the per-query value if
   *  the two fetches race — without this, page loads where the SSE
   *  handshake resolved before /api/deployment did would still end
   *  up with the boot deployment in the store. */
  private lockedForQuery = false;

  /** Load the server's boot-time deployment. Idempotent. Respects
   *  the per-query lock so a slow boot fetch can't clobber a chip
   *  the SSE handshake already pivoted. */
  async load(): Promise<void> {
    if (this.loaded || this.lockedForQuery) return;
    try {
      const r = await fetch('/api/deployment');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // Recheck the lock after the await — setForQuery() may have
      // landed during the fetch.
      if (this.lockedForQuery) return;
      this.current = (await r.json()) as Deployment;
      this.loaded = true;
    } catch (e) {
      this.error = String(e);
    }
  }

  /** Update the chip to reflect the deployment that was actually
   *  routed-to for the current query — called by the /q/[queryId] SSE
   *  handler when the backend emits the `deployment` event. Fetches
   *  /api/deployment?deployment=<name> to pick up the right city +
   *  hazard strings; without that the chip would just show the raw
   *  directory name and miss the deployment-specific hazard text.
   *  When name is null (out-of-coverage), falls back to a neutral
   *  chip rather than claiming a city we don't have. */
  async setForQuery(name: string | null): Promise<void> {
    this.lockedForQuery = true;  // claim ownership against load() races
    if (!name) {
      this.current = {
        name: 'unknown',
        city: 'Not in any shipped deployment',
        hazard: 'Climate-exposure briefing',
      };
      this.loaded = true;
      return;
    }
    if (this.current?.name === name && this.loaded) return;
    try {
      const r = await fetch('/api/deployment?deployment=' + encodeURIComponent(name));
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.current = (await r.json()) as Deployment;
      this.loaded = true;
    } catch (e) {
      this.error = String(e);
    }
  }
}

export const deployment = new DeploymentStore();
