/**
 * Standalone test presets for the chat widget's dev-only preset selector (panel mi-presets,
 * substep 8.4.1).
 *
 * Reads the ONE canonical list in `knowledge-base/config/standalone_presets.json` via the `@kb/*`
 * path alias — the SAME file the backend reads and validates through the real gate
 * (`backend/app/features/rag_agent/application/standalone_presets.py`). One source, the
 * platforms.json pattern: the frontend never defines a preset, it only renders the
 * backend-validated list. A preset is a simulated verified-context shape (company_id + the three
 * §D.13 slots); it never widens access (the backend gate is the boundary — never-bend rules 2–3).
 */
import presetsFile from "@kb/config/standalone_presets.json";
import { isLocalOrDevEnv } from "@/features/embed";

export interface PresetSlots {
  pos: string | null;
  pms: string | null;
  accounting: string | null;
}

export interface StandalonePreset {
  id: string;
  label: string;
  /** A §D.2 flow direction, or `three_system` for the Toast/Mews/QuickBooks workflow. */
  flowType: string;
  companyId: string;
  slots: PresetSlots;
}

interface RawPreset {
  id: string;
  label: string;
  flow_type: string;
  company_id: string;
  slots: { pos: string | null; pms: string | null; accounting: string | null };
}

interface RawPresetsFile {
  presets: RawPreset[];
}

export const STANDALONE_PRESETS: readonly StandalonePreset[] = (
  presetsFile as RawPresetsFile
).presets.map((raw) => ({
  id: raw.id,
  label: raw.label,
  flowType: raw.flow_type,
  companyId: raw.company_id,
  slots: {
    pos: raw.slots.pos,
    pms: raw.slots.pms,
    accounting: raw.slots.accounting,
  },
}));

/**
 * True only in the standalone/test environment (local/dev/test/ci). The preset selector is a
 * test-harness control, never shown against a real customer configuration — same dev-only gate the
 * home page's embed test-host links use (`app/(site)/page.tsx`). Reuses the embed feature's
 * edge-safe env signal through its public root.
 */
export function isStandaloneEnv(): boolean {
  return isLocalOrDevEnv();
}
