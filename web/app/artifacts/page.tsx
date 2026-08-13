/**
 * Artifacts view: browse constraints / agent context / evals from output/.
 */

import { Suspense } from "react";
import { ArtifactsPanel } from "@/components/artifacts_panel";

/**
 * Tabbed artifact browser.
 *
 * The panel reads the `scanned` search param, so it renders inside Suspense to
 * keep this route statically prerenderable.
 */
export default function ArtifactsPage() {
  return (
    <main>
      <h1>Artifacts</h1>
      <p className="lede">
        Output from the last scan. Copy agent context into your agent loop when you
        need treatment-arm behavior.
      </p>
      <Suspense fallback={<p className="status">Loading…</p>}>
        <ArtifactsPanel />
      </Suspense>
    </main>
  );
}
