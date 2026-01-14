import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";
import { InlineDocumentEmbedComponent } from "./InlineDocumentEmbedComponent";

export interface InlineDocumentEmbedOptions {
  HTMLAttributes: Record<string, unknown>;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    inlineDocumentEmbed: {
      /**
       * Insert an inline document embed showing full content
       */
      insertInlineDocumentEmbed: (attrs: {
        documentId: string;
        title: string;
        icon?: string | null;
      }) => ReturnType;
      /**
       * Toggle collapse state of an inline document embed
       */
      toggleEmbedCollapse: (pos: number) => ReturnType;
    };
  }
}

export const InlineDocumentEmbedExtension = Node.create<InlineDocumentEmbedOptions>({
  name: "inlineDocumentEmbed",

  group: "block",

  atom: true,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      documentId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-document-id"),
        renderHTML: (attributes) => ({
          "data-document-id": attributes.documentId,
        }),
      },
      title: {
        default: "",
        parseHTML: (element) => element.getAttribute("data-title"),
        renderHTML: (attributes) => ({
          "data-title": attributes.title,
        }),
      },
      icon: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-icon"),
        renderHTML: (attributes) => ({
          "data-icon": attributes.icon,
        }),
      },
      isCollapsed: {
        default: false,
        parseHTML: (element) => element.getAttribute("data-collapsed") === "true",
        renderHTML: (attributes) => ({
          "data-collapsed": attributes.isCollapsed ? "true" : "false",
        }),
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-type="inline-document-embed"]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(
        { "data-type": "inline-document-embed" },
        this.options.HTMLAttributes,
        HTMLAttributes
      ),
      0,
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(InlineDocumentEmbedComponent);
  },

  addCommands() {
    return {
      insertInlineDocumentEmbed:
        (attrs) =>
        ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: {
              ...attrs,
              isCollapsed: false,
            },
          });
        },
      toggleEmbedCollapse:
        (pos) =>
        ({ tr, dispatch }) => {
          const node = tr.doc.nodeAt(pos);
          if (node?.type.name !== this.name) return false;

          if (dispatch) {
            tr.setNodeMarkup(pos, undefined, {
              ...node.attrs,
              isCollapsed: !node.attrs.isCollapsed,
            });
          }
          return true;
        },
    };
  },
});

export default InlineDocumentEmbedExtension;
