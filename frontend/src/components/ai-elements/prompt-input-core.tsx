"use client";

import { InputGroup } from "@/components/ui/input-group";
import { cn } from "@/lib/utils";
import type { FileUIPart } from "ai";
import { useCallback, useRef, type FormEventHandler } from "react";
import {
  LocalAttachmentsContext,
  LocalReferencedSourcesContext,
} from "./prompt-input-provider";
import type { PromptInputProps } from "./prompt-input-types";
import { convertBlobUrlToDataUrl } from "./prompt-input-utils";
import { usePromptInputAttachments } from "./use-prompt-input-attachments";
import { usePromptInputSources } from "./use-prompt-input-sources";

export { type PromptInputMessage, type PromptInputProps } from "./prompt-input-types";

export const PromptInput = ({
  className,
  accept,
  multiple,
  globalDrop,
  syncHiddenInput,
  maxFiles,
  maxFileSize,
  onError,
  onSubmit,
  children,
  ...props
}: PromptInputProps) => {
  const formRef = useRef<HTMLFormElement | null>(null);
  const {
    context: attachmentsContext,
    controller,
    files,
    handleChange,
    inputRef,
  } = usePromptInputAttachments({
    accept,
    formRef,
    globalDrop,
    maxFileSize,
    maxFiles,
    onError,
    syncHiddenInput,
  });
  const { clear: clearSources, context: sourcesContext } =
    usePromptInputSources();
  const usingProvider = controller !== null;

  const clear = useCallback(() => {
    attachmentsContext.clear();
    clearSources();
  }, [attachmentsContext, clearSources]);

  const handleSubmit: FormEventHandler<HTMLFormElement> = useCallback(
    async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const text = usingProvider
        ? controller.textInput.value
        : ((new FormData(form).get("message") as string) || "");

      if (!usingProvider) {
        form.reset();
      }

      try {
        const convertedFiles: FileUIPart[] = await Promise.all(
          files.map(async (attachment) => {
            const file = { ...attachment };
            Reflect.deleteProperty(file, "id");
            if (file.url?.startsWith("blob:")) {
              return {
                ...file,
                url: (await convertBlobUrlToDataUrl(file.url)) ?? file.url,
              };
            }
            return file;
          }),
        );
        const result = onSubmit({ files: convertedFiles, text }, event);

        if (result instanceof Promise) {
          try {
            await result;
            clear();
            if (usingProvider) {
              controller.textInput.clear();
            }
          } catch {
            // Keep attachments and text available for a retry.
          }
        } else {
          clear();
          if (usingProvider) {
            controller.textInput.clear();
          }
        }
      } catch {
        // Keep attachments and text available if conversion or submission fails.
      }
    },
    [clear, controller, files, onSubmit, usingProvider],
  );

  return (
    <LocalAttachmentsContext.Provider value={attachmentsContext}>
      <LocalReferencedSourcesContext.Provider value={sourcesContext}>
        <input
          accept={accept}
          aria-label="Upload files"
          className="hidden"
          multiple={multiple}
          onChange={handleChange}
          ref={inputRef}
          title="Upload files"
          type="file"
        />
        <form
          className={cn("w-full", className)}
          onSubmit={handleSubmit}
          ref={formRef}
          {...props}
        >
          <InputGroup className="overflow-hidden">{children}</InputGroup>
        </form>
      </LocalReferencedSourcesContext.Provider>
    </LocalAttachmentsContext.Provider>
  );
};
