/**
 * StandalonePresetBar — the standalone/test environment's simulated-context picker (panel
 * mi-presets, substep 8.4.1).
 *
 * Renders ONLY in the standalone env (local/dev/test/ci); a real customer session never sees it.
 * It shows a clearly-labelled "simulated test context" marker so a tester can never mistake a
 * pretend setup for real configuration (§D.8), and a select of the backend-validated presets.
 * Selecting a preset starts a FRESH chat (`selectSimulatedPreset` → `restart`), so two simulated
 * contexts never share a conversation.
 *
 * The presets are the backend-validated list (`model/standalone-presets.ts` reads the same
 * `knowledge-base/config/standalone_presets.json` the backend gate validates). This bar only
 * reflects the selection; threading the simulated context into the outgoing request/token is a
 * later substep (8.4.2). It is NOT a parallel code path and never widens access.
 */
"use client";

import {
  STANDALONE_PRESETS,
  isStandaloneEnv,
  type StandalonePreset,
} from "../model/standalone-presets";
import { useChatSession } from "./chat-session-provider";

export function StandalonePresetBar() {
  const { simulatedPreset, selectSimulatedPreset } = useChatSession();

  // Dev-only harness control — never rendered against a real customer configuration.
  if (!isStandaloneEnv() || STANDALONE_PRESETS.length === 0) return null;

  function onChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const next: StandalonePreset | undefined = STANDALONE_PRESETS.find(
      (preset) => preset.id === event.target.value,
    );
    selectSimulatedPreset(next);
  }

  return (
    <div
      data-testid="simulated-context-marker"
      className="flex flex-none flex-col gap-[4px] border-b border-border bg-accent-bg px-md py-[8px]"
    >
      <span className="text-[11px] font-semibold uppercase tracking-wide text-accent">
        Simulated test context — not a real customer configuration
      </span>
      <label className="flex items-center gap-sm text-[12px] text-text-muted">
        <span className="font-medium text-text">Preset</span>
        <select
          aria-label="Simulated test context preset"
          value={simulatedPreset?.id ?? ""}
          onChange={onChange}
          className="flex-1 rounded-sm border border-border bg-surface px-[8px] py-[4px] text-[12px] text-text"
        >
          <option value="">No preset (general only)</option>
          {STANDALONE_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
