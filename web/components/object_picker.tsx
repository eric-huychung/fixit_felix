/**
 * Searchable combobox for picking a scannable sObject from the org.
 */

"use client";

import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Spinner } from "@/components/loading";
import { fetch_objects } from "@/lib/api_client";
import type { sobject_summary } from "@/lib/types";

type props = {
  value: string;
  on_change: (name: string) => void;
  disabled?: boolean;
  /** Rendered on the same row as the search control (primary button, …). */
  actions?: ReactNode;
};

type loaded = { objects: sobject_summary[] } | { failed: true };

/**
 * Lists the org's scannable objects in a searchable combobox.
 *
 * When the list call fails, falls back to a plain text field so a known API
 * name can still be typed (connection errors surface on Run Scan / Diagnose).
 *
 * @param props - Selection and optional trailing actions
 */
export function ObjectPicker({ value, on_change, disabled, actions }: props) {
  const [loaded, set_loaded] = useState<loaded | null>(null);
  const [query, set_query] = useState("");
  const [open, set_open] = useState(false);
  const [active, set_active] = useState(0);
  const root_ref = useRef<HTMLDivElement | null>(null);
  const list_id = useId();

  useEffect(() => {
    let current = true;

    fetch_objects()
      .then((objects) => {
        if (current) set_loaded({ objects });
      })
      .catch(() => {
        if (current) set_loaded({ failed: true });
      });

    return () => {
      current = false;
    };
  }, []);

  useEffect(() => {
    function on_pointer(event: MouseEvent) {
      if (!root_ref.current?.contains(event.target as Node)) set_open(false);
    }
    document.addEventListener("mousedown", on_pointer);
    return () => document.removeEventListener("mousedown", on_pointer);
  }, []);

  const objects = loaded && "objects" in loaded ? loaded.objects : null;
  const failed = loaded !== null && "failed" in loaded;

  const selected = objects?.find((obj) => obj.name === value) ?? null;
  const filter_text = open ? query : "";
  const filtered = useMemo(
    () => filter_objects(objects ?? [], filter_text),
    [objects, filter_text],
  );
  const active_index = filtered.length === 0 ? 0 : Math.min(active, filtered.length - 1);

  if (failed) {
    return (
      <div className="field">
        <span className="field_head">Object</span>
        <div className="control_row">
          <input
            value={value}
            onChange={(e) => on_change(e.target.value)}
            disabled={disabled}
            spellCheck={false}
            aria-describedby="object_picker_hint"
          />
          {actions}
        </div>
        <span id="object_picker_hint" className="hint">
          Could not list objects — type an API name.
        </span>
      </div>
    );
  }

  if (objects === null) {
    return (
      <div className="field">
        <span className="field_head">Object</span>
        <div className="control_row">
          <span className="control_loading">
            <Spinner label="Loading objects" />
          </span>
          {actions}
        </div>
      </div>
    );
  }

  const input_value = open ? query : display_query(selected, value);

  function pick(name: string) {
    on_change(name);
    set_query("");
    set_open(false);
  }

  function on_key(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      set_open(true);
      set_active((index) => Math.min(index + 1, Math.max(filtered.length - 1, 0)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      set_active((index) => Math.max(index - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const choice = filtered[active_index];
      if (open && choice) pick(choice.name);
      else set_open(true);
      return;
    }
    if (event.key === "Escape") {
      set_open(false);
      set_query("");
    }
  }

  return (
    <div className="field" ref={root_ref}>
      <span className="field_head">
        Object
        <span className="field_meta">{objects.length}</span>
      </span>
      <div className="control_row">
        <div className="combobox">
          <input
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls={list_id}
            aria-autocomplete="list"
            aria-activedescendant={
              open && filtered[active_index]
                ? `${list_id}-${filtered[active_index].name}`
                : undefined
            }
            disabled={disabled}
            spellCheck={false}
            placeholder="Search objects…"
            value={input_value}
            onChange={(e) => {
              set_query(e.target.value);
              set_active(0);
              set_open(true);
            }}
            onFocus={() => {
              set_query("");
              set_active(0);
              set_open(true);
            }}
            onKeyDown={on_key}
          />
          {open ? (
            <ul className="combobox_list" role="listbox" id={list_id}>
              {filtered.length === 0 ? (
                <li className="combobox_empty">No matches</li>
              ) : (
                filtered.map((obj, index) => (
                  <li
                    key={obj.name}
                    role="option"
                    id={`${list_id}-${obj.name}`}
                    aria-selected={obj.name === value}
                  >
                    <button
                      type="button"
                      className={
                        index === active_index ? "combobox_option active" : "combobox_option"
                      }
                      onMouseEnter={() => set_active(index)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pick(obj.name)}
                    >
                      <span className="combobox_label">{obj.label}</span>
                      {obj.label !== obj.name ? (
                        <span className="combobox_api">{obj.name}</span>
                      ) : null}
                      {obj.custom ? <span className="combobox_tag">custom</span> : null}
                    </button>
                  </li>
                ))
              )}
            </ul>
          ) : null}
        </div>
        {actions}
      </div>
    </div>
  );
}

function display_query(selected: sobject_summary | null, value: string): string {
  if (!selected) return value;
  return selected.label === selected.name ? selected.name : `${selected.label} (${selected.name})`;
}

/** Keep objects whose API name or label contains the query. */
function filter_objects(objects: sobject_summary[], query: string): sobject_summary[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return objects;
  return objects.filter(
    (obj) => obj.name.toLowerCase().includes(needle) || obj.label.toLowerCase().includes(needle),
  );
}
