/**
 * Hard empty state when the last scan has no active validation rules.
 */

/**
 * Test cases / context / eval tabs need active rules.
 */
export function NoActiveRulesNotice({ object_name }: { object_name?: string | null }) {
  const where = object_name ? ` on ${object_name}` : "";
  return (
    <div className="artifact_view" role="alert">
      <p className="status error">No active validation rules{where}.</p>
      <p className="section_note">Scan an object that has rules (e.g. Opportunity).</p>
    </div>
  );
}
