"use client";

import { useApiStatus } from "@/components/ApiStatusProvider";
import { fetchEvents, isNotFoundError } from "@/lib/api";
import { copy } from "@/lib/copy";
import { linkClass } from "@/lib/ui";
import { useClientFetch } from "@/lib/use-client-fetch";
import type { EventsResponse } from "@/lib/types";

export function EventsList({ identifier }: { identifier: string }) {
  const api = useApiStatus();
  const enabled = api.status === "ok" && Boolean(identifier);
  const state = useClientFetch<EventsResponse | null>(
    `events:${identifier}`,
    async () => {
      try {
        return await fetchEvents(identifier);
      } catch (error) {
        if (isNotFoundError(error)) {
          return null;
        }
        throw error;
      }
    },
    { enabled },
  );

  if (!enabled || state.status === "loading" || state.status === "error") {
    return null;
  }
  const events = state.data?.events ?? [];
  if (events.length === 0) {
    return null;
  }

  return (
    <section
      aria-label={copy.events.title}
      className="rounded-2xl border border-border bg-surface px-4 py-3 text-sm text-foreground"
    >
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {copy.events.title}
      </h2>
      <ul className="flex flex-col gap-2">
        {events.slice(0, 8).map((event) => (
          <li key={event.external_id} className="border-t border-border/70 pt-2 first:border-t-0 first:pt-0">
            <p className="text-xs text-muted">
              {event.occurred_at.slice(0, 10)} · {event.event_type} · {event.source}
            </p>
            {event.url ? (
              <a href={event.url} className={linkClass} target="_blank" rel="noreferrer">
                {event.headline}
              </a>
            ) : (
              <p>{event.headline}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
