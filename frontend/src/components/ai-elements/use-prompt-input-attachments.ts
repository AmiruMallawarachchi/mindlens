"use client";

import type { FileUIPart } from "ai";
import type { ChangeEventHandler, RefObject } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useOptionalPromptInputController,
  type AttachmentsContext,
} from "./prompt-input-provider";
import type { PromptInputProps } from "./prompt-input-types";
import { createFileParts, getAcceptedFiles, limitFiles } from "./prompt-input-utils";
import { usePromptInputDrop } from "./use-prompt-input-drop";

type PromptInputAttachmentOptions = Pick<
  PromptInputProps,
  "accept" | "globalDrop" | "maxFileSize" | "maxFiles" | "onError" | "syncHiddenInput"
> & {
  formRef: RefObject<HTMLFormElement | null>;
};

/** Manage local or provider-owned attachments for one prompt form. */
export function usePromptInputAttachments({
  accept,
  formRef,
  globalDrop,
  maxFileSize,
  maxFiles,
  onError,
  syncHiddenInput,
}: PromptInputAttachmentOptions) {
  const controller = useOptionalPromptInputController();
  const usingProvider = controller !== null;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [localFiles, setLocalFiles] = useState<
    (FileUIPart & { id: string })[]
  >([]);
  const files = usingProvider ? controller.attachments.files : localFiles;
  const filesRef = useRef(files);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  const openLocalFileDialog = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const addLocal = useCallback(
    (fileList: File[] | FileList) => {
      const accepted = getAcceptedFiles(fileList, accept, maxFileSize, onError);
      if (accepted.length === 0) {
        return;
      }
      setLocalFiles((previous) => {
        const capped = limitFiles(accepted, previous.length, maxFiles, onError);
        return [...previous, ...createFileParts(capped)];
      });
    },
    [accept, maxFileSize, maxFiles, onError],
  );

  const addToProvider = useCallback(
    (fileList: File[] | FileList) => {
      const accepted = getAcceptedFiles(fileList, accept, maxFileSize, onError);
      const capped = limitFiles(accepted, files.length, maxFiles, onError);
      if (capped.length > 0) {
        controller?.attachments.add(capped);
      }
    },
    [accept, controller, files.length, maxFileSize, maxFiles, onError],
  );

  const removeLocal = useCallback((id: string) => {
    setLocalFiles((previous) => {
      const file = previous.find((item) => item.id === id);
      if (file?.url) {
        URL.revokeObjectURL(file.url);
      }
      return previous.filter((item) => item.id !== id);
    });
  }, []);

  const clearLocal = useCallback(() => {
    setLocalFiles((previous) => {
      for (const file of previous) {
        if (file.url) {
          URL.revokeObjectURL(file.url);
        }
      }
      return [];
    });
  }, []);

  const add = usingProvider ? addToProvider : addLocal;
  const remove = controller?.attachments.remove ?? removeLocal;
  const clear = controller?.attachments.clear ?? clearLocal;
  const openFileDialog = controller?.attachments.openFileDialog ?? openLocalFileDialog;

  useEffect(() => {
    if (controller) {
      controller.__registerFileInput(inputRef, openLocalFileDialog);
    }
  }, [controller, openLocalFileDialog]);

  useEffect(() => {
    if (syncHiddenInput && inputRef.current && files.length === 0) {
      inputRef.current.value = "";
    }
  }, [files, syncHiddenInput]);

  usePromptInputDrop(formRef, globalDrop, add);

  useEffect(
    () => () => {
      if (!usingProvider) {
        for (const file of filesRef.current) {
          if (file.url) {
            URL.revokeObjectURL(file.url);
          }
        }
      }
    },
    [usingProvider],
  );

  const handleChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (event) => {
      if (event.currentTarget.files) {
        add(event.currentTarget.files);
      }
      event.currentTarget.value = "";
    },
    [add],
  );

  const context = useMemo<AttachmentsContext>(
    () => ({
      add,
      clear,
      fileInputRef: inputRef,
      files: files.map((file) => ({ ...file, id: file.id })),
      openFileDialog,
      remove,
    }),
    [add, clear, files, openFileDialog, remove],
  );

  return { context, controller, files, handleChange, inputRef, usingProvider };
}
