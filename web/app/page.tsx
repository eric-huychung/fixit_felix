/**
 * Home / Scan view: headline strip + run scan.
 */

import { HeadlineStrip } from "@/components/headline_strip";
import { ScanPanel } from "@/components/scan_panel";

/**
 * Primary Scan composition for the local UI.
 */
export default function HomePage() {
  return (
    <main>
      <h1>Scan</h1>
      <p className="lede">
        Point Felix at your org, extract write-path constraints, and refresh local
        artifacts — without memorizing CLI flags.
      </p>
      <HeadlineStrip />
      <ScanPanel />
    </main>
  );
}
