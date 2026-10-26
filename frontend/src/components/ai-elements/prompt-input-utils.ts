import type { FileUIPart } from "ai";
import { nanoid } from "nanoid";

export const convertBlobUrlToDataUrl = async (
  url: string,
): Promise<string | null> => {
  try {
    const response = await fetch(url);
    const blob = await response.blob();
    // FileReader uses callback-based API, wrapping in Promise is necessary
    // oxlint-disable-next-line eslint-plugin-promise(avoid-new)
    return new Promise((resolve) => {
      const reader = new FileReader();
      // oxlint-disable-next-line eslint-plugin-unicorn(prefer-add-event-listener)
      reader.onloadend = () => resolve(reader.result as string);
      // oxlint-disable-next-line eslint-plugin-unicorn(prefer-add-event-listener)
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
};

export const captureScreenshot = async (): Promise<File | null> => {
  if (
    typeof navigator === "undefined" ||
    !navigator.mediaDevices?.getDisplayMedia
  ) {
    return null;
  }

  let stream: MediaStream | null = null;
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;

  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      audio: false,
      video: true,
    });

    video.srcObject = stream;

    // Video element uses callback-based API, wrapping in Promise is necessary
    // oxlint-disable-next-line eslint-plugin-promise(avoid-new)
    await new Promise<void>((resolve, reject) => {
      // oxlint-disable-next-line eslint-plugin-unicorn(prefer-add-event-listener)
      video.onloadedmetadata = () => resolve();
      // oxlint-disable-next-line eslint-plugin-unicorn(prefer-add-event-listener)
      video.onerror = () => reject(new Error("Failed to load screen stream"));
    });

    await video.play();

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return null;
    }

    context.drawImage(video, 0, 0, width, height);
    // canvas.toBlob uses callback-based API, wrapping in Promise is necessary
    // oxlint-disable-next-line eslint-plugin-promise(avoid-new)
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/png");
    });
    if (!blob) {
      return null;
    }

    const timestamp = new Date()
      .toISOString()
      .replaceAll(/[:.]/g, "-")
      .replace("T", "_")
      .replace("Z", "");

    return new File([blob], `screenshot-${timestamp}.png`, {
      lastModified: Date.now(),
      type: "image/png",
    });
  } finally {
    if (stream) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
    }
    video.pause();
    video.srcObject = null;
  }
};

export type PromptInputFileError = {
  code: "max_files" | "max_file_size" | "accept";
  message: string;
};

export type PromptInputOnError = (error: PromptInputFileError) => void;

export function getAcceptedFiles(
  fileList: File[] | FileList,
  accept: string | undefined,
  maxFileSize: number | undefined,
  onError: PromptInputOnError | undefined,
): File[] {
  const incoming = [...fileList];
  const patterns = accept
    ?.split(",")
    .map((pattern) => pattern.trim())
    .filter(Boolean);
  const accepted = patterns?.length
    ? incoming.filter((file) =>
        patterns.some((pattern) =>
          pattern.endsWith("/*")
            ? file.type.startsWith(pattern.slice(0, -1))
            : file.type === pattern,
        ),
      )
    : incoming;

  if (incoming.length > 0 && accepted.length === 0) {
    onError?.({
      code: "accept",
      message: "No files match the accepted types.",
    });
    return [];
  }

  const sized = maxFileSize
    ? accepted.filter((file) => file.size <= maxFileSize)
    : accepted;
  if (accepted.length > 0 && sized.length === 0) {
    onError?.({
      code: "max_file_size",
      message: "All files exceed the maximum size.",
    });
    return [];
  }
  return sized;
}

export function limitFiles(
  incoming: File[],
  existingCount: number,
  maxFiles: number | undefined,
  onError: PromptInputOnError | undefined,
): File[] {
  if (typeof maxFiles !== "number") {
    return incoming;
  }
  const capacity = Math.max(0, maxFiles - existingCount);
  if (incoming.length > capacity) {
    onError?.({
      code: "max_files",
      message: "Too many files. Some were not added.",
    });
  }
  return incoming.slice(0, capacity);
}

export function createFileParts(files: File[]): (FileUIPart & { id: string })[] {
  return files.map((file) => ({
    filename: file.name,
    id: nanoid(),
    mediaType: file.type,
    type: "file",
    url: URL.createObjectURL(file),
  }));
}
