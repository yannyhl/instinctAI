import { useState, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import { ReactRenderer } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import Suggestion, { type SuggestionOptions, type SuggestionProps } from "@tiptap/suggestion";
import tippy, { type Instance as TippyInstance } from "tippy.js";
import { FileText, Search, Link2, FileCode } from "lucide-react";
import { cn } from "@/lib/utils";

export type InsertMode = "link" | "embed";

export interface DocumentSuggestionItem {
  id: string;
  title: string;
  icon: string | null;
  insertMode?: InsertMode;
}

interface DocumentListProps {
  items: DocumentSuggestionItem[];
  command: (item: DocumentSuggestionItem) => void;
  query: string;
}

interface DocumentListRef {
  onKeyDown: (props: { event: KeyboardEvent }) => boolean;
}

const DocumentList = forwardRef<DocumentListRef, DocumentListProps>(
  ({ items, command, query }, ref) => {
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [insertMode, setInsertMode] = useState<InsertMode>("link");

    const selectItem = useCallback(
      (index: number) => {
        const item = items[index];
        if (item) {
          command({ ...item, insertMode });
        }
      },
      [items, command, insertMode]
    );

    useEffect(() => {
      setSelectedIndex(0);
    }, [items]);

    useImperativeHandle(ref, () => ({
      onKeyDown: ({ event }: { event: KeyboardEvent }) => {
        if (event.key === "ArrowUp") {
          setSelectedIndex((prev) => (prev + items.length - 1) % items.length);
          return true;
        }
        if (event.key === "ArrowDown") {
          setSelectedIndex((prev) => (prev + 1) % items.length);
          return true;
        }
        if (event.key === "Enter") {
          selectItem(selectedIndex);
          return true;
        }
        // Tab to toggle mode
        if (event.key === "Tab") {
          event.preventDefault();
          setInsertMode((prev) => (prev === "link" ? "embed" : "link"));
          return true;
        }
        return false;
      },
    }));

    if (items.length === 0) {
      return (
        <div className="bg-popover border rounded-lg shadow-lg p-3 min-w-[280px]">
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Search className="h-4 w-4" />
            <span>No documents found for "{query}"</span>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-popover border rounded-lg shadow-lg py-1 min-w-[280px] max-h-[350px] overflow-y-auto">
        {/* Mode selector */}
        <div className="px-2 py-1.5 border-b border-border mb-1">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setInsertMode("link")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-2 py-1 text-xs rounded",
                "transition-colors",
                insertMode === "link"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              )}
            >
              <Link2 className="h-3 w-3" />
              Link
            </button>
            <button
              type="button"
              onClick={() => setInsertMode("embed")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-2 py-1 text-xs rounded",
                "transition-colors",
                insertMode === "embed"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              )}
            >
              <FileCode className="h-3 w-3" />
              Embed
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-1 text-center">
            Press Tab to toggle
          </p>
        </div>

        {/* Document list */}
        <div className="px-2 py-1 text-xs text-muted-foreground font-medium uppercase tracking-wider">
          {insertMode === "link" ? "Link to document" : "Embed document content"}
        </div>
        {items.map((item, index) => (
          <button
            key={item.id}
            onClick={() => selectItem(index)}
            className={cn(
              "w-full flex items-center gap-2 px-2 py-1.5 text-sm text-left",
              "hover:bg-accent transition-colors",
              index === selectedIndex && "bg-accent"
            )}
          >
            {item.icon ? (
              <span className="text-base flex-shrink-0">{item.icon}</span>
            ) : (
              <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            )}
            <span className="truncate">{item.title || "Untitled"}</span>
          </button>
        ))}
      </div>
    );
  }
);

DocumentList.displayName = "DocumentList";

export interface DocumentSuggestionOptions {
  suggestion: Partial<SuggestionOptions<DocumentSuggestionItem>>;
}

export const DocumentSuggestion = Extension.create<DocumentSuggestionOptions>({
  name: "documentSuggestion",

  addOptions() {
    return {
      suggestion: {
        char: "[[",
        startOfLine: false,
        items: () => [],
        render: () => {
          let component: ReactRenderer<DocumentListRef> | null = null;
          let popup: TippyInstance[] | null = null;

          return {
            onStart: (props: SuggestionProps<DocumentSuggestionItem>) => {
              component = new ReactRenderer(DocumentList, {
                props,
                editor: props.editor,
              });

              if (!props.clientRect) return;

              popup = tippy("body", {
                getReferenceClientRect: props.clientRect as () => DOMRect,
                appendTo: () => document.body,
                content: component.element,
                showOnCreate: true,
                interactive: true,
                trigger: "manual",
                placement: "bottom-start",
              });
            },

            onUpdate: (props: SuggestionProps<DocumentSuggestionItem>) => {
              component?.updateProps(props);

              if (!props.clientRect) return;

              popup?.[0]?.setProps({
                getReferenceClientRect: props.clientRect as () => DOMRect,
              });
            },

            onKeyDown: (props: { event: KeyboardEvent }) => {
              if (props.event.key === "Escape") {
                popup?.[0]?.hide();
                return true;
              }

              return component?.ref?.onKeyDown(props) ?? false;
            },

            onExit: () => {
              popup?.[0]?.destroy();
              component?.destroy();
            },
          };
        },
      },
    };
  },

  addProseMirrorPlugins() {
    return [
      Suggestion({
        editor: this.editor,
        ...this.options.suggestion,
      }),
    ];
  },
});

export default DocumentSuggestion;
