import { useCallback, useRef, useEffect, type FC, type MutableRefObject } from "react";
import { motion } from "framer-motion";
import { useDroppable } from "@dnd-kit/core";
import { Loader2, FileText } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { DocumentHeader } from "./DocumentHeader";
import { DocumentEditor } from "./DocumentEditor";
import { BacklinksPanel } from "./BacklinksPanel";
import { cn } from "@/lib/utils";
import type { DocumentWithLinks, TipTapDocument } from "@shared/schema";

interface InsertFunctions {
  insertLink: (documentId: string, title: string, icon?: string | null) => void;
  insertEmbed: (documentId: string, title: string, icon?: string | null) => void;
}

interface AvailableDocument {
  id: string;
  title: string;
  icon: string | null;
}

interface DocumentViewerProps {
  document: DocumentWithLinks | null;
  isLoading: boolean;
  onUpdateTitle: (title: string) => void;
  onUpdateIcon: (icon: string | null) => void;
  onUpdateStatus: (status: "draft" | "published" | "archived") => void;
  onUpdateContent: (content: TipTapDocument) => void;
  onDelete: () => void;
  onNavigate: (id: string) => void;
  canEdit: boolean;
  onInsertLinkRef?: MutableRefObject<((documentId: string, title: string, icon?: string | null) => void) | null>;
  onInsertFunctionsRef?: MutableRefObject<InsertFunctions | null>;
  /** Available documents for [[ link suggestions */
  availableDocuments?: AvailableDocument[];
  /** Project ID for embedded document fetching */
  projectId?: string;
}

export const DocumentViewer: FC<DocumentViewerProps> = ({
  document,
  isLoading,
  onUpdateTitle,
  onUpdateIcon,
  onUpdateStatus,
  onUpdateContent,
  onDelete,
  onNavigate,
  canEdit,
  onInsertLinkRef,
  onInsertFunctionsRef,
  availableDocuments = [],
  projectId,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);

  // Droppable zone for drag-and-drop document links
  const { setNodeRef, isOver } = useDroppable({
    id: "document-editor-drop-zone",
    data: {
      type: "editor",
    },
  });

  // Handle document drop to insert inline link
  const insertDocumentLink = useCallback(
    (documentId: string, title: string, icon?: string | null) => {
      const insertLinkEl = editorRef.current?.querySelector("[data-insert-link]") as any;
      if (insertLinkEl?.insertDocumentLink) {
        insertLinkEl.insertDocumentLink(documentId, title, icon);
      }
    },
    []
  );

  // Handle document drop to insert block embed
  const insertDocumentEmbed = useCallback(
    (documentId: string, title: string, icon?: string | null) => {
      const insertLinkEl = editorRef.current?.querySelector("[data-insert-link]") as any;
      if (insertLinkEl?.insertDocumentEmbed) {
        insertLinkEl.insertDocumentEmbed(documentId, title, icon);
      }
    },
    []
  );

  // Expose the insert link function to the parent via ref (legacy)
  useEffect(() => {
    if (onInsertLinkRef) {
      onInsertLinkRef.current = insertDocumentLink;
    }
    return () => {
      if (onInsertLinkRef) {
        onInsertLinkRef.current = null;
      }
    };
  }, [onInsertLinkRef, insertDocumentLink]);

  // Expose both insert functions via ref
  useEffect(() => {
    if (onInsertFunctionsRef) {
      onInsertFunctionsRef.current = {
        insertLink: insertDocumentLink,
        insertEmbed: insertDocumentEmbed,
      };
    }
    return () => {
      if (onInsertFunctionsRef) {
        onInsertFunctionsRef.current = null;
      }
    };
  }, [onInsertFunctionsRef, insertDocumentLink, insertDocumentEmbed]);

  // Empty state
  if (!document && !isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
        <FileText className="h-12 w-12 mb-4 opacity-50" />
        <p className="text-lg font-medium">No document selected</p>
        <p className="text-sm">Select a document from the sidebar or create a new one</p>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!document) return null;

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "h-full flex flex-col",
        isOver && "ring-2 ring-primary/50 ring-inset rounded-lg"
      )}
    >
      <ScrollArea className="flex-1">
        <motion.div
          key={document.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="p-4 pl-6 pr-8"
          ref={editorRef}
        >
          {/* Header */}
          <DocumentHeader
            document={document}
            onUpdateTitle={onUpdateTitle}
            onUpdateIcon={onUpdateIcon}
            onUpdateStatus={onUpdateStatus}
            onDelete={onDelete}
            canEdit={canEdit}
          />

          {/* Editor */}
          <DocumentEditor
            content={document.content}
            onUpdate={onUpdateContent}
            onNavigateToDocument={onNavigate}
            editable={canEdit}
            placeholder="Type [[ to link documents, or start typing..."
            className="min-h-[300px]"
            availableDocuments={availableDocuments}
            currentDocumentId={document.id}
            projectId={projectId}
          />

          {/* Backlinks */}
          {document.backlinks && document.backlinks.length > 0 && (
            <BacklinksPanel
              backlinks={document.backlinks}
              onNavigate={onNavigate}
            />
          )}
        </motion.div>
      </ScrollArea>

      {/* Drop zone overlay */}
      {isOver && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 bg-primary/5 pointer-events-none flex items-center justify-center"
        >
          <div className="bg-background border rounded-lg px-4 py-3 shadow-lg text-center">
            <p className="text-sm font-medium">Drop to insert inline link</p>
            <p className="text-xs text-muted-foreground mt-1">Hold Shift to embed as card</p>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default DocumentViewer;
