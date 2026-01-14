import { useState, useEffect, useCallback, useRef, useMemo, type FC } from "react";
import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Link from "@tiptap/extension-link";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Dropcursor from "@tiptap/extension-dropcursor";
import { DocumentLinkExtension } from "./extensions/DocumentLinkExtension";
import { DocumentEmbedExtension } from "./extensions/DocumentEmbedExtension";
import { InlineDocumentEmbedExtension } from "./extensions/InlineDocumentEmbedExtension";
import { DocumentSuggestion, type DocumentSuggestionItem } from "./extensions/DocumentSuggestion";
import { EmbedContextProvider } from "./extensions/EmbedContext";
import type { TipTapDocument } from "@shared/schema";
import { cn } from "@/lib/utils";

interface DocumentEditorProps {
  content: TipTapDocument | null;
  onUpdate: (content: TipTapDocument) => void;
  onNavigateToDocument: (documentId: string) => void;
  editable?: boolean;
  placeholder?: string;
  className?: string;
  /** Available documents for [[ suggestion */
  availableDocuments?: DocumentSuggestionItem[];
  /** Current document ID to exclude from suggestions */
  currentDocumentId?: string;
  /** Project ID for embedded document fetching */
  projectId?: string;
}

export const DocumentEditor: FC<DocumentEditorProps> = ({
  content,
  onUpdate,
  onNavigateToDocument,
  editable = true,
  placeholder = "Type [[ to link documents, or just start typing...",
  className,
  availableDocuments = [],
  currentDocumentId,
  projectId,
}) => {
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  // Track when we're the source of an update to avoid sync conflicts
  const isLocalUpdateRef = useRef(false);
  const lastSavedContentRef = useRef<string | null>(null);
  // Track when a document is being dragged over the editor
  const [isDragOver, setIsDragOver] = useState(false);

  // Debounced update handler
  const handleUpdate = useCallback(
    (editor: Editor) => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      // Mark that we have pending local changes
      isLocalUpdateRef.current = true;

      debounceRef.current = setTimeout(() => {
        const json = editor.getJSON() as TipTapDocument;
        // Store what we're saving so we can recognize it when it comes back
        lastSavedContentRef.current = JSON.stringify(json);
        onUpdate(json);

        // Reset the flag after a short delay to allow the save to complete
        setTimeout(() => {
          isLocalUpdateRef.current = false;
        }, 1000);
      }, 800);
    },
    [onUpdate]
  );

  // Filter out current document from suggestions
  const filteredDocuments = useMemo(() => {
    return availableDocuments.filter((doc) => doc.id !== currentDocumentId);
  }, [availableDocuments, currentDocumentId]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
        dropcursor: false, // Disable default, we'll use our own
      }),
      Dropcursor.configure({
        color: "hsl(var(--primary))",
        width: 2,
        class: "drop-cursor",
      }),
      Placeholder.configure({
        placeholder,
        emptyEditorClass: "is-editor-empty",
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: "text-primary underline hover:text-primary/80",
        },
      }),
      TaskList.configure({
        HTMLAttributes: {
          class: "task-list",
        },
      }),
      TaskItem.configure({
        nested: true,
        HTMLAttributes: {
          class: "task-item",
        },
      }),
      DocumentLinkExtension.configure({
        onNavigate: onNavigateToDocument,
      }),
      DocumentEmbedExtension,
      InlineDocumentEmbedExtension,
      DocumentSuggestion.configure({
        suggestion: {
          items: ({ query }: { query: string }) => {
            const lowerQuery = query.toLowerCase();
            return filteredDocuments
              .filter((doc) =>
                doc.title.toLowerCase().includes(lowerQuery)
              )
              .slice(0, 8);
          },
          command: ({ editor, range, props }: any) => {
            // Delete the [[ trigger text and insert based on mode
            const insertMode = props.insertMode || "link";

            if (insertMode === "embed") {
              // Insert inline document embed with full content
              editor
                .chain()
                .focus()
                .deleteRange(range)
                .insertContent({
                  type: "inlineDocumentEmbed",
                  attrs: {
                    documentId: props.id,
                    title: props.title,
                    icon: props.icon,
                    isCollapsed: false,
                  },
                })
                .run();
            } else {
              // Insert inline document link (pill)
              editor
                .chain()
                .focus()
                .deleteRange(range)
                .insertContent([
                  {
                    type: "documentLink",
                    attrs: {
                      documentId: props.id,
                      title: props.title,
                      icon: props.icon,
                    },
                  },
                  { type: "text", text: " " },
                ])
                .run();
            }
          },
        },
      }),
    ],
    content: content || undefined,
    editable,
    onUpdate: ({ editor }) => {
      handleUpdate(editor);
    },
    editorProps: {
      attributes: {
        class: cn(
          "prose prose-sm dark:prose-invert max-w-none",
          "focus:outline-none min-h-[200px] p-4"
        ),
      },
    },
  });

  // Update content when it changes externally (not from our own edits)
  useEffect(() => {
    if (!editor || !content) return;

    // Skip if we have pending local changes - this prevents conflicts while typing
    if (isLocalUpdateRef.current) return;

    const newContent = JSON.stringify(content);

    // Skip if this is the same content we just saved
    if (lastSavedContentRef.current === newContent) return;

    const currentContent = JSON.stringify(editor.getJSON());
    if (currentContent !== newContent) {
      // Only update if the editor is not focused (user not actively editing)
      if (!editor.isFocused) {
        editor.commands.setContent(content);
        lastSavedContentRef.current = newContent;
      }
    }
  }, [editor, content]);

  // Update editable state
  useEffect(() => {
    if (editor) {
      editor.setEditable(editable);
    }
  }, [editor, editable]);

  // Handle document link clicks
  useEffect(() => {
    const handleLinkClick = (e: Event) => {
      const customEvent = e as CustomEvent<{ documentId: string }>;
      if (customEvent.detail?.documentId) {
        onNavigateToDocument(customEvent.detail.documentId);
      }
    };

    document.addEventListener("document-link-click", handleLinkClick);
    return () => {
      document.removeEventListener("document-link-click", handleLinkClick);
    };
  }, [onNavigateToDocument]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  // Handle native drag over to allow drop
  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes("application/x-document-link")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      setIsDragOver(true);
    }
  }, []);

  // Handle drag leave
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    // Only set false if we're leaving the editor container
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
    }
  }, []);

  // Handle native drop to insert at exact cursor position
  const handleDrop = useCallback((e: React.DragEvent) => {
    setIsDragOver(false);
    const data = e.dataTransfer.getData("application/x-document-link");
    if (!data || !editor) return;

    e.preventDefault();
    e.stopPropagation();

    try {
      const { id, title, icon } = JSON.parse(data);

      // Get the position in the editor from the drop coordinates
      const view = editor.view;
      const pos = view.posAtCoords({ left: e.clientX, top: e.clientY });

      if (pos) {
        // Check if Shift is held for embed vs link
        const isShiftHeld = e.shiftKey;

        // Set selection to drop position
        editor.chain().focus().setTextSelection(pos.pos).run();

        if (isShiftHeld) {
          // Insert embed block
          editor
            .chain()
            .focus()
            .insertContent({
              type: "documentEmbed",
              attrs: { documentId: id, title, icon },
            })
            .run();
        } else {
          // Insert inline link
          editor
            .chain()
            .focus()
            .insertContent([
              {
                type: "documentLink",
                attrs: { documentId: id, title, icon },
              },
              { type: "text", text: " " },
            ])
            .run();
        }
      }
    } catch (err) {
      console.error("Failed to handle document drop:", err);
    }
  }, [editor]);

  // Insert inline document link - appears inline with text
  const insertDocumentLink = useCallback(
    (documentId: string, title: string, icon?: string | null) => {
      if (!editor) return;

      const docSize = editor.state.doc.content.size;

      if (docSize <= 2) {
        // Empty document - insert a paragraph with the link
        editor
          .chain()
          .focus()
          .insertContent([
            {
              type: "paragraph",
              content: [
                {
                  type: "documentLink",
                  attrs: { documentId, title, icon },
                },
                { type: "text", text: " " },
              ],
            },
          ])
          .run();
      } else {
        // Document has content - insert inline at cursor position
        editor
          .chain()
          .focus()
          .insertContent([
            {
              type: "documentLink",
              attrs: { documentId, title, icon },
            },
            { type: "text", text: " " },
          ])
          .run();
      }
    },
    [editor]
  );

  // Insert document embed - block-level card
  const insertDocumentEmbed = useCallback(
    (documentId: string, title: string, icon?: string | null) => {
      if (!editor) return;

      editor
        .chain()
        .focus()
        .insertContent({
          type: "documentEmbed",
          attrs: { documentId, title, icon },
        })
        .run();
    },
    [editor]
  );

  return (
    <EmbedContextProvider
      projectId={projectId || ""}
      currentNestingDepth={0}
      documentIdStack={currentDocumentId ? [currentDocumentId] : []}
      onNavigate={onNavigateToDocument}
    >
      <div
        className={cn(
          "document-editor relative",
          isDragOver && "ring-2 ring-primary/50 ring-inset rounded bg-primary/5",
          className
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <EditorContent editor={editor} />

        {/* Drop hint overlay */}
        {isDragOver && (
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center bg-primary/5">
            <div className="px-3 py-1.5 bg-background border rounded-md shadow-sm text-xs text-muted-foreground">
              Drop to insert link • Hold Shift for embed
            </div>
          </div>
        )}

        {/* Expose insert methods via data attribute */}
        <div
          data-insert-link
          style={{ display: "none" }}
          ref={(el) => {
            if (el) {
              (el as any).insertDocumentLink = insertDocumentLink;
              (el as any).insertDocumentEmbed = insertDocumentEmbed;
            }
          }}
        />
      </div>
    </EmbedContextProvider>
  );
};

// Export editor type for ref access
export type { Editor };

export default DocumentEditor;
