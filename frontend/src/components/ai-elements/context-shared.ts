import type { LanguageModelUsage } from "ai";
import { createContext, useContext } from "react";

type ModelId = string;

export interface ContextSchema {
  usedTokens: number;
  maxTokens: number;
  usage?: LanguageModelUsage;
  modelId?: ModelId;
}

export const ContextContext = createContext<ContextSchema | null>(null);

export const useContextValue = () => {
  const context = useContext(ContextContext);
  if (!context) {
    throw new Error("Context components must be used within Context");
  }
  return context;
};
