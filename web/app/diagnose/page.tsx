/**
 * Diagnose view: paste a Salesforce error and resolve the real rule.
 */

import { DiagnosePanel } from "@/components/diagnose_panel";

/**
 * Diagnose composition for useless-admin and other write failures.
 */
export default function DiagnosePage() {
  return (
    <main>
      <h1>Diagnose</h1>
      <p className="lede">
        Paste a Salesforce write error. Felix matches it to the scanned rule — even
        when the message is useless.
      </p>
      <DiagnosePanel />
    </main>
  );
}
