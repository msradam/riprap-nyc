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

  async load(): Promise<void> {
    if (this.loaded) return;
    try {
      const r = await fetch('/api/deployment');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      this.current = (await r.json()) as Deployment;
      this.loaded = true;
    } catch (e) {
      this.error = String(e);
    }
  }
}

export const deployment = new DeploymentStore();
