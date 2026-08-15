/**
 * Icon button that copies text to the clipboard and confirms in place.
 */

"use client";

import { useEffect, useState } from "react";
import { AlertIcon, CheckIcon, CopyIcon } from "@/components/icons";

type copy_state = "idle" | "copied" | "failed";

const RESET_MS = 2000;

const TITLES: Record<copy_state, string> = {
  idle: "Copy to clipboard",
  copied: "Copied",
  failed: "Your browser blocked clipboard access",
};

/**
 * Copies `text` on click.
 *
 * Clipboard writes reject outside a secure context or when the user denies
 * permission, so failure is shown rather than swallowed.
 *
 * @param props - The text to copy
 */
export function CopyButton({ text }: { text: string }) {
  const [state, set_state] = useState<copy_state>("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => set_state("idle"), RESET_MS);
    return () => clearTimeout(timer);
  }, [state]);

  async function on_click() {
    try {
      await navigator.clipboard.writeText(text);
      set_state("copied");
    } catch {
      set_state("failed");
    }
  }

  return (
    <button
      type="button"
      className="icon_button"
      onClick={on_click}
      title={TITLES[state]}
      aria-label={TITLES[state]}
    >
      {state === "copied" ? <CheckIcon className="ok" /> : null}
      {state === "failed" ? <AlertIcon className="bad" /> : null}
      {state === "idle" ? <CopyIcon /> : null}
    </button>
  );
}
