import { nanoid } from "nanoid";
import { useCallback, useMemo, useState } from "react";
import type { SourceDocumentUIPart } from "ai";
import type { ReferencedSourcesContext } from "./prompt-input-provider";

/** Own the source references attached to a single PromptInput instance. */
export function usePromptInputSources() {
  const [sources, setSources] = useState<
    (SourceDocumentUIPart & { id: string })[]
  >([]);

  const clear = useCallback(() => setSources([]), []);
  const context = useMemo<ReferencedSourcesContext>(
    () => ({
      add: (incoming) => {
        const items = Array.isArray(incoming) ? incoming : [incoming];
        setSources((previous) => [
          ...previous,
          ...items.map((source) => ({ ...source, id: nanoid() })),
        ]);
      },
      clear,
      remove: (id) =>
        setSources((previous) => previous.filter((source) => source.id !== id)),
      sources,
    }),
    [clear, sources],
  );

  return { clear, context };
}
