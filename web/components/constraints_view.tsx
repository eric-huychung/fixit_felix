/**
 * Readable constraints inventory: rules first, then write-blocking fields.
 */

import { short_soap_type } from "@/lib/parse_artifacts";
import type { apex_constraint, field_constraint, scan_result, validation_rule_constraint } from "@/lib/types";

/**
 * Renders a scan result as cards and a compact field table — not a markdown dump.
 *
 * @param props - Parsed scan_result.json
 */
export function ConstraintsView({ result }: { result: scan_result }) {
  const active = result.rules.filter((rule) => rule.active).length;
  const blocking = result.fields.filter(is_write_blocking);
  const inactive = result.rules.length - active;

  return (
    <div className="artifact_view">
      <div className="summary_row">
        <span className="chip">
          {active} active rule{active === 1 ? "" : "s"}
        </span>
        {inactive ? <span className="chip">{inactive} inactive</span> : null}
        <span className="chip">
          {blocking.length} write-blocking field{blocking.length === 1 ? "" : "s"}
        </span>
        {result.apex.length ? <span className="chip">{result.apex.length} Apex</span> : null}
        {result.errors.length ? (
          <span className="chip warn">
            {result.errors.length} scan error{result.errors.length === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>

      {result.errors.length ? <ErrorsList errors={result.errors} /> : null}

      <section>
        <h2>Validation rules</h2>
        {result.rules.length === 0 ? (
          <p className="status">No validation rules on this object.</p>
        ) : (
          result.rules.map((rule) => <RuleCard key={rule.id} rule={rule} />)
        )}
      </section>

      <section>
        <h2>Write-blocking fields</h2>
        <p className="section_note">Required, picklist, and lookup fields an agent has to get right.</p>
        {blocking.length === 0 ? (
          <p className="status">No required, picklist, or lookup fields.</p>
        ) : (
          <div className="table_wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Constraint</th>
                </tr>
              </thead>
              <tbody>
                {blocking.map((field) => (
                  <tr key={field.api_name}>
                    <td>
                      <code>{field.api_name}</code>
                      {field.label !== field.api_name ? (
                        <span className="muted"> {field.label}</span>
                      ) : null}
                    </td>
                    <td>{field_constraint_label(field)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {result.apex.length ? (
        <section>
          <h2>Apex addError</h2>
          {result.apex.map((item) => (
            <ApexCard key={item.source_name} item={item} />
          ))}
        </section>
      ) : null}
    </div>
  );
}

function RuleCard({ rule }: { rule: validation_rule_constraint }) {
  return (
    <article className="card">
      <header className="card_head">
        <h3>{rule.name}</h3>
        <span className={`badge ${rule.active ? "ok" : "muted"}`}>
          {rule.active ? "active" : "inactive"}
        </span>
        {rule.namespace_prefix ? <span className="badge">{rule.namespace_prefix}</span> : null}
      </header>
      <p className="meaning">{rule.plain_english || "No translation yet — formula below."}</p>
      <dl className="meta">
        <div>
          <dt>Error</dt>
          <dd>{rule.error_message}</dd>
        </div>
        {rule.fields_referenced.length ? (
          <div>
            <dt>Fields</dt>
            <dd>
              <ChipList values={rule.fields_referenced} />
            </dd>
          </div>
        ) : null}
      </dl>
      <details>
        <summary>Formula</summary>
        <pre className="formula">{rule.formula}</pre>
      </details>
    </article>
  );
}

function ApexCard({ item }: { item: apex_constraint }) {
  return (
    <article className="card">
      <header className="card_head">
        <h3>{item.source_name}</h3>
        <span className={`badge ${item.confidence === "high" ? "ok" : "muted"}`}>{item.confidence}</span>
      </header>
      <p className="meaning">
        {item.error_messages.length ? item.error_messages.join(" · ") : "Message unknown (dynamic)."}
      </p>
      <details>
        <summary>Excerpt</summary>
        <pre className="formula">{item.excerpt}</pre>
      </details>
    </article>
  );
}

function ErrorsList({ errors }: { errors: scan_result["errors"] }) {
  return (
    <section>
      <h2>Scan errors</h2>
      <p className="section_note">These stages failed, so the inventory may be incomplete.</p>
      <ul className="error_list">
        {errors.map((err, index) => (
          <li key={`${err.stage}-${err.target}-${index}`}>
            <strong>
              {err.stage} / {err.target}
            </strong>
            <span>{first_line(err.message)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ChipList({ values }: { values: string[] }) {
  return (
    <span className="chips">
      {values.map((value) => (
        <span className="chip" key={value}>
          {value}
        </span>
      ))}
    </span>
  );
}

function is_write_blocking(field: field_constraint): boolean {
  return field.required || field.picklist_values.length > 0 || field.reference_to.length > 0;
}

function field_constraint_label(field: field_constraint): string {
  const parts = [short_soap_type(field.soap_type)];
  if (field.required) parts.push("required");
  if (field.picklist_values.length) {
    const shown = field.picklist_values.slice(0, 4).join(", ");
    const extra = field.picklist_values.length - 4;
    parts.push(extra > 0 ? `${shown} +${extra}` : shown);
  }
  if (field.reference_to.length) parts.push(`→ ${field.reference_to.join(", ")}`);
  if (field.max_length && !field.picklist_values.length) parts.push(`max ${field.max_length}`);
  return parts.join(" · ");
}

function first_line(message: string): string {
  const line = message.split("\n")[0] ?? message;
  return line.length > 180 ? `${line.slice(0, 177)}…` : line;
}
