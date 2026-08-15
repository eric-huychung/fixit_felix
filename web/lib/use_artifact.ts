/**
 * Hook for loading one artifact from output/ via the loopback API.
 */

"use client";

import { useEffect, useState } from "react";
import { fetch_artifact } from "@/lib/api_client";

export type artifact_state = {
  content: string | null;
  error: string | null;
  loading: boolean;
};

type loaded = {
  name: string;
  content: string | null;
  error: string | null;
};

/**
 * Loads an artifact and tracks its request lifecycle.
 *
 * A response is tagged with the name it was requested for, so a slow fetch
 * cannot overwrite a tab the user has already left.
 *
 * @param name - Artifact basename, e.g. scan_result.json
 * @returns Content, error, and whether a request is still in flight
 */
export function useArtifact(name: string): artifact_state {
  const [loaded, set_loaded] = useState<loaded | null>(null);

  useEffect(() => {
    let current = true;

    fetch_artifact(name)
      .then((artifact) => {
        if (current) set_loaded({ name, content: artifact.content, error: null });
      })
      .catch((err: unknown) => {
        if (!current) return;
        const message = err instanceof Error ? err.message : `Failed to load ${name}`;
        set_loaded({ name, content: null, error: message });
      });

    return () => {
      current = false;
    };
  }, [name]);

  if (loaded?.name !== name) {
    return { content: null, error: null, loading: true };
  }
  return { content: loaded.content, error: loaded.error, loading: false };
}
