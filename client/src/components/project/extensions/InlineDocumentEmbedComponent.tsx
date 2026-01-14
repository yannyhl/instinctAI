import { type FC, useState, useMemo, useCallback } from "react";
import { NodeViewWrapper, type NodeViewProps, useEditor, EditorContent } from "@tiptap/react";
import { FileText, ExternalLink, ChevronDown, ChevronRight, RefreshCw, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useEmbedContext, canEmbed, MAX_EMBED_DEPTH, EmbedContextProvider } from "./EmbedContext";
import { useEmbeddedDocument } from "@/hooks/useDocuments";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

// TipTap extensions for read-only content rendering
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Link from "@tiptap/extension-link";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";

interface ReadOnlyEditorProps {
  content: unknown;
  projectId: string;
  nestingDepth: number;
  documentIdStack: string[];
  onNavigate: (documentId: string) => void;
}

const ReadOnlyEditor: FC<ReadOnlyEditorProps> = ({
  content,
  projectId,
  nestingDepth,
  documentIdStack,
  onNavigate,
}) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: "Empty document",
      }),
      Link.configure({
        openOnClick: true,
        HTMLAttributes: {
          class: "text-primary underline",
        },
      }),
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
    ],
    content: content || { type: "doc", content: [] },
    editable: false,
    editorProps: {
      attributes: {
        class: "prose prose-sm max-w-none focus:outline-none",
      },
    },
  });

  if (!editor) {
    return <Skeleton className="h-20 w-full" />;
  }

  return (
    <EmbedContextProvider
      projectId={projectId}
      currentNestingDepth={nestingDepth}
      documentIdStack={documentIdStack}
      onNavigate={onNavigate}
    >
      <EditorContent editor={editor} />
    </EmbedContextProvider>
  );
};

export const InlineDocumentEmbedComponent: FC<NodeViewProps> = ({
  node,
  updateAttributes,
  selected,
  getPos,
}) => {
  const { documentId, title, icon, isCollapsed } = node.attrs;
  const embedContext = useEmbedContext();
  const [retryCount, setRetryCount] = useState(0);

  // Get context values or defaults (for top-level renders outside context)
  const projectId = embedContext?.projectId ?? "";
  const currentDepth = embedContext?.currentNestingDepth ?? 0;
  const parentStack = embedContext?.documentIdStack ?? [];
  const onNavigate = embedContext?.onNavigate;

  // Check if we can embed this document
  const embedCheck = useMemo(
    () => canEmbed(documentId, currentDepth, parentStack),
    [documentId, currentDepth, parentStack]
  );

  // Fetch document content (only if allowed and projectId exists)
  const {
    data: document,
    isLoading,
    error,
    refetch,
  } = useEmbeddedDocument(
    embedCheck.allowed ? projectId : undefined,
    embedCheck.allowed ? documentId : undefined
  );

  const handleNavigate = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (onNavigate) {
      onNavigate(documentId);
    } else {
      // Fallback: dispatch custom event
      const event = new CustomEvent("document-link-click", {
        detail: { documentId },
        bubbles: true,
      });
      e.currentTarget.dispatchEvent(event);
    }
  };

  const handleToggleCollapse = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    updateAttributes({ isCollapsed: !isCollapsed });
  };

  const handleRetry = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setRetryCount((c) => c + 1);
    refetch();
  };

  // New document stack with current document added (if documentId is valid)
  const newDocumentStack = useMemo(
    () => (documentId ? [...parentStack, documentId] : parentStack),
    [parentStack, documentId]
  );

  // Stable fallback for onNavigate
  const handleNavigateForChild = useCallback(
    (docId: string) => {
      if (onNavigate) {
        onNavigate(docId);
      }
    },
    [onNavigate]
  );

  return (
    <NodeViewWrapper className="inline-document-embed-wrapper my-3">
      <div
        className={cn(
          "rounded-lg border border-border overflow-hidden",
          "bg-muted/30",
          selected && "ring-2 ring-primary"
        )}
        contentEditable={false}
      >
        {/* Header */}
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-2",
            "bg-muted/50 border-b border-border",
            "cursor-pointer hover:bg-muted/70 transition-colors"
          )}
          onClick={handleToggleCollapse}
        >
          {/* Collapse toggle */}
          <button
            type="button"
            className="p-0.5 hover:bg-accent rounded"
            onClick={handleToggleCollapse}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>

          {/* Icon */}
          {icon ? (
            <span className="text-base flex-shrink-0">{icon}</span>
          ) : (
            <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
          )}

          {/* Title */}
          <span className="flex-1 font-medium text-sm truncate">
            {document?.title || title || "Untitled"}
          </span>

          {/* Navigate button */}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleNavigate}
            title="Open document"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Content area */}
        {!isCollapsed && (
          <div className="relative">
            {/* Left border indicator */}
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary/20" />

            <div className="pl-4 pr-3 py-3">
              {/* Not allowed to embed */}
              {!embedCheck.allowed && (
                <div className="flex items-center gap-2 text-amber-600 text-sm">
                  <AlertCircle className="h-4 w-4" />
                  <span>{embedCheck.reason}</span>
                </div>
              )}

              {/* Missing project context */}
              {embedCheck.allowed && !projectId && (
                <div className="flex items-center gap-2 text-muted-foreground text-sm">
                  <AlertCircle className="h-4 w-4" />
                  <span>Cannot load embed outside of project context</span>
                </div>
              )}

              {/* Loading state */}
              {embedCheck.allowed && projectId && isLoading && (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              )}

              {/* Error state */}
              {embedCheck.allowed && projectId && error && !isLoading && (
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertCircle className="h-4 w-4" />
                  <span>Failed to load document</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2"
                    onClick={handleRetry}
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Retry
                  </Button>
                </div>
              )}

              {/* Content */}
              {embedCheck.allowed && projectId && document && !isLoading && (
                <ReadOnlyEditor
                  content={document.content}
                  projectId={projectId}
                  nestingDepth={currentDepth + 1}
                  documentIdStack={newDocumentStack}
                  onNavigate={handleNavigateForChild}
                />
              )}

              {/* Empty document */}
              {embedCheck.allowed &&
                projectId &&
                document &&
                !isLoading &&
                !document.content && (
                  <div className="text-muted-foreground text-sm italic">
                    Empty document
                  </div>
                )}
            </div>
          </div>
        )}
      </div>
    </NodeViewWrapper>
  );
};

export default InlineDocumentEmbedComponent;
