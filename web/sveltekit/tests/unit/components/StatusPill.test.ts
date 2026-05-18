/**
 * StatusPill — the top-right "gathering evidence · X · n/m" indicator.
 * Two bugs landed here:
 *   - stuck visible after run completed (phase never transitioned
 *     to 'done' in no-LLM templated mode → pill never hid)
 *   - showed "Resolving address" fallback text after streaming ended
 *
 * The pill is now phase-driven via briefingState. This file is the
 * state-machine regression seal.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import StatusPill from '$lib/components/shell/StatusPill.svelte';
import { briefingState } from '$lib/stores/briefingState.svelte';

beforeEach(() => {
  briefingState.reset();
});

describe('StatusPill visibility per phase', () => {
  it('hidden when phase=idle', () => {
    briefingState.phase = 'idle';
    const { container } = render(StatusPill);
    expect(container.querySelector('.status')).toBeNull();
  });

  it('hidden when phase=done (post-run, the bug)', () => {
    // The user-reported failure: after the briefing finished the pill
    // was still showing "gathering evidence · X · 9/10". Once phase
    // transitions to 'done', it must hide.
    briefingState.phase = 'done';
    briefingState.firedCount = 10;
    briefingState.totalSpecialists = 10;
    const { container } = render(StatusPill);
    expect(container.querySelector('.status')).toBeNull();
  });

  it.each(['planning', 'specialists', 'reconciling', 'streaming', 'error'] as const)(
    'visible when phase=%s',
    (phase) => {
      briefingState.phase = phase;
      if (phase === 'error') briefingState.errorMessage = 'something broke';
      const { container } = render(StatusPill);
      expect(container.querySelector('.status')).not.toBeNull();
    },
  );
});

describe('StatusPill content per phase', () => {
  it('phase=specialists with progress → "gathering evidence" + "fired/total"', () => {
    briefingState.phase = 'specialists';
    briefingState.activeStep = 'floodnet';
    briefingState.firedCount = 8;
    briefingState.totalSpecialists = 11;
    const { container } = render(StatusPill);
    const text = container.textContent ?? '';
    expect(text).toContain('gathering evidence');
    expect(text).toContain('FloodNet sensors');
    expect(text).toContain('8/11');
  });

  it('phase=streaming with attempt=2 → "writing (reroll 1)"', () => {
    briefingState.phase = 'streaming';
    briefingState.attempt = 2;
    const { container } = render(StatusPill);
    expect(container.textContent ?? '').toContain('reroll 1');
  });

  it('phase=error → red border + error message', () => {
    briefingState.phase = 'error';
    briefingState.errorMessage = 'planner timed out';
    const { container } = render(StatusPill);
    const pill = container.querySelector('.status');
    expect(pill?.getAttribute('data-kind')).toBe('err');
    expect(container.textContent ?? '').toContain('planner timed out');
  });
});
