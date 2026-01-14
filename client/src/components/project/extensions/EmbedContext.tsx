import { createContext, useContext, type ReactNode, type FC } from "react";

interface EmbedContextValue {
  projectId: string;
  currentNestingDepth: number;
  documentIdStack: string[];
  onNavigate: (documentId: string) => void;
}

const EmbedContext = createContext<EmbedContextValue | null>(null);

interface EmbedContextProviderProps {
  children: ReactNode;
  projectId: string;
  currentNestingDepth?: number;
  documentIdStack?: string[];
  onNavigate: (documentId: string) => void;
}

export const EmbedContextProvider: FC<EmbedContextProviderProps> = ({
  children,
  projectId,
  currentNestingDepth = 0,
  documentIdStack = [],
  onNavigate,
}) => {
  return (
    <EmbedContext.Provider
      value={{
        projectId,
        currentNestingDepth,
        documentIdStack,
        onNavigate,
      }}
    >
      {children}
    </EmbedContext.Provider>
  );
};

export function useEmbedContext(): EmbedContextValue | null {
  return useContext(EmbedContext);
}

export function useRequiredEmbedContext(): EmbedContextValue {
  const context = useContext(EmbedContext);
  if (!context) {
    throw new Error("useRequiredEmbedContext must be used within EmbedContextProvider");
  }
  return context;
}

export const MAX_EMBED_DEPTH = 3;

export function isCircularReference(
  documentId: string,
  documentIdStack: string[]
): boolean {
  return documentIdStack.includes(documentId);
}

export function canEmbed(
  documentId: string,
  currentDepth: number,
  documentIdStack: string[]
): { allowed: boolean; reason?: string } {
  if (currentDepth >= MAX_EMBED_DEPTH) {
    return { allowed: false, reason: "Maximum nesting depth reached" };
  }
  if (isCircularReference(documentId, documentIdStack)) {
    return { allowed: false, reason: "Circular reference detected" };
  }
  return { allowed: true };
}
