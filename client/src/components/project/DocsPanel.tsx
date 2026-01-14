import { useState, useCallback, useMemo, useRef, useEffect, type FC } from "react";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type Modifier,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useToast } from "@/hooks/use-toast";
import { DocumentSidebar } from "./DocumentSidebar";
import { DocumentViewer } from "./DocumentViewer";
import { DocumentBreadcrumbs } from "./DocumentBreadcrumbs";
import { CreateDocumentDialog, flattenTreeForSelect } from "./CreateDocumentDialog";
import { getNodeContext, findNodeById } from "./DocumentTree";
import {
  useDocumentTree,
  useDocument,
  useCreateDocument,
  useUpdateDocument,
  useDeleteDocument,
  useReorderDocuments,
} from "@/hooks/useDocuments";
import type { DocumentTreeNode, TipTapDocument } from "@shared/schema";

interface DocsPanelProps {
  projectId: string;
  canEdit: boolean;
}

/**
 * Builds breadcrumb path from root to a document
 */
function buildBreadcrumbs(
  nodes: DocumentTreeNode[],
  targetId: string,
  path: { id: string; title: string; icon: string | null }[] = []
): { id: string; title: string; icon: string | null }[] | null {
  for (const node of nodes) {
    const currentPath = [...path, { id: node.id, title: node.title, icon: node.icon }];
    if (node.id === targetId) {
      return currentPath;
    }
    const found = buildBreadcrumbs(node.children, targetId, currentPath);
    if (found) return found;
  }
  return null;
}

export const DocsPanel: FC<DocsPanelProps> = ({ projectId, canEdit }) => {
  const { toast } = useToast();

  // State
  const [currentDocumentId, setCurrentDocumentId] = useState<string | null>(null);
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [activeDragNode, setActiveDragNode] = useState<DocumentTreeNode | null>(null);
  const [isShiftHeld, setIsShiftHeld] = useState(false);

  // Ref to call insert link on the viewer
  const insertLinkRef = useRef<((documentId: string, title: string, icon?: string | null) => void) | null>(null);
  const insertFunctionsRef = useRef<{
    insertLink: (documentId: string, title: string, icon?: string | null) => void;
    insertEmbed: (documentId: string, title: string, icon?: string | null) => void;
  } | null>(null);

  // Track shift key state for embed vs link insertion
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Shift") setIsShiftHeld(true);
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Shift") setIsShiftHeld(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Custom modifier to position overlay at cursor
  const snapToCursor: Modifier = useCallback(({ transform, activatorEvent, draggingNodeRect }) => {
    if (!activatorEvent || !draggingNodeRect) {
      return transform;
    }

    // Get the mouse position from the activator event
    const activatorCoordinates = {
      x: (activatorEvent as PointerEvent).clientX,
      y: (activatorEvent as PointerEvent).clientY,
    };

    // Offset to position the overlay nicely near cursor (top-left corner follows cursor)
    return {
      ...transform,
      x: activatorCoordinates.x - draggingNodeRect.left + transform.x - 10,
      y: activatorCoordinates.y - draggingNodeRect.top + transform.y - 10,
    };
  }, []);

  // Queries
  const { data: treeData, isLoading: isTreeLoading } = useDocumentTree(projectId);
  const { data: currentDocument, isLoading: isDocLoading } = useDocument(
    projectId,
    currentDocumentId || undefined
  );

  // Mutations
  const createMutation = useCreateDocument(projectId);
  const updateMutation = useUpdateDocument(projectId);
  const deleteMutation = useDeleteDocument(projectId);
  const reorderMutation = useReorderDocuments(projectId);

  const tree = treeData || [];

  // Flatten tree to get all documents for [[ suggestion
  const flattenedDocuments = useMemo(() => {
    const result: { id: string; title: string; icon: string | null }[] = [];
    function flatten(nodes: DocumentTreeNode[]) {
      for (const node of nodes) {
        result.push({ id: node.id, title: node.title, icon: node.icon });
        if (node.children.length > 0) {
          flatten(node.children);
        }
      }
    }
    flatten(tree);
    return result;
  }, [tree]);

  // Breadcrumbs
  const breadcrumbs = useMemo(() => {
    if (!currentDocumentId || !tree.length) return [];
    return buildBreadcrumbs(tree, currentDocumentId) || [];
  }, [tree, currentDocumentId]);

  // Parent options for create dialog
  const parentOptions = useMemo(() => flattenTreeForSelect(tree), [tree]);

  // Navigation
  const navigateToDocument = useCallback((id: string) => {
    if (currentDocumentId && currentDocumentId !== id) {
      setNavigationHistory((prev) => [...prev, currentDocumentId]);
    }
    setCurrentDocumentId(id);
  }, [currentDocumentId]);

  const navigateBack = useCallback(() => {
    const previousId = navigationHistory.at(-1);
    if (previousId) {
      setNavigationHistory((prev) => prev.slice(0, -1));
      setCurrentDocumentId(previousId);
    }
  }, [navigationHistory]);

  const navigateHome = useCallback(() => {
    setCurrentDocumentId(null);
    setNavigationHistory([]);
  }, []);

  // CRUD handlers
  const handleCreate = useCallback(
    async (data: { title: string; parentId: string | null; icon: string | null }) => {
      try {
        const result = await createMutation.mutateAsync({
          title: data.title,
          parentId: data.parentId,
          icon: data.icon,
        });
        setIsCreateDialogOpen(false);
        if (result.data?.id) {
          navigateToDocument(result.data.id);
        }
        toast({
          title: "Document created",
          description: `"${data.title}" has been created successfully.`,
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to create document. Please try again.",
          variant: "destructive",
        });
      }
    },
    [createMutation, navigateToDocument, toast]
  );

  const handleUpdateTitle = useCallback(
    async (title: string) => {
      if (!currentDocumentId) return;
      try {
        await updateMutation.mutateAsync({
          id: currentDocumentId,
          data: { title },
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to update title.",
          variant: "destructive",
        });
      }
    },
    [currentDocumentId, updateMutation, toast]
  );

  const handleUpdateIcon = useCallback(
    async (icon: string | null) => {
      if (!currentDocumentId) return;
      try {
        await updateMutation.mutateAsync({
          id: currentDocumentId,
          data: { icon },
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to update icon.",
          variant: "destructive",
        });
      }
    },
    [currentDocumentId, updateMutation, toast]
  );

  const handleUpdateStatus = useCallback(
    async (status: "draft" | "published" | "archived") => {
      if (!currentDocumentId) return;
      try {
        await updateMutation.mutateAsync({
          id: currentDocumentId,
          data: { status },
        });
        toast({
          title: "Status updated",
          description: `Document is now ${status}.`,
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to update status.",
          variant: "destructive",
        });
      }
    },
    [currentDocumentId, updateMutation, toast]
  );

  const handleUpdateContent = useCallback(
    async (content: TipTapDocument) => {
      if (!currentDocumentId) return;
      try {
        await updateMutation.mutateAsync({
          id: currentDocumentId,
          data: { content },
        });
      } catch (error) {
        // Silently fail for content updates (debounced)
        console.error("Failed to save content:", error);
      }
    },
    [currentDocumentId, updateMutation]
  );

  const handleDelete = useCallback(
    async (id?: string) => {
      const targetId = id || currentDocumentId;
      if (!targetId) return;

      try {
        await deleteMutation.mutateAsync(targetId);
        if (targetId === currentDocumentId) {
          navigateBack();
        }
        toast({
          title: "Document deleted",
          description: "The document has been moved to trash.",
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to delete document.",
          variant: "destructive",
        });
      }
    },
    [currentDocumentId, deleteMutation, navigateBack, toast]
  );

  const handleReorder = useCallback(
    async (updates: { id: string; parentId: string | null; sortOrder: number }[]) => {
      try {
        await reorderMutation.mutateAsync(updates);
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to reorder documents.",
          variant: "destructive",
        });
      }
    },
    [reorderMutation, toast]
  );

  // Rename document from sidebar
  const handleRename = useCallback(
    async (id: string, newTitle: string) => {
      try {
        await updateMutation.mutateAsync({
          id,
          data: { title: newTitle },
        });
        toast({
          title: "Renamed",
          description: `Document renamed to "${newTitle}"`,
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to rename document.",
          variant: "destructive",
        });
      }
    },
    [updateMutation, toast]
  );

  // Duplicate document
  const handleDuplicate = useCallback(
    async (id: string) => {
      // Find the document in the tree to get its info
      const node = findNodeById(tree, id);
      if (!node) {
        toast({
          title: "Error",
          description: "Document not found.",
          variant: "destructive",
        });
        return;
      }

      try {
        // Create a copy with "(Copy)" appended to title
        const result = await createMutation.mutateAsync({
          title: `${node.title} (Copy)`,
          parentId: node.parentId || null,
          icon: node.icon,
        });

        if (result.data?.id) {
          navigateToDocument(result.data.id);
        }

        toast({
          title: "Duplicated",
          description: `Created copy of "${node.title}"`,
        });
      } catch (error) {
        toast({
          title: "Error",
          description: "Failed to duplicate document.",
          variant: "destructive",
        });
      }
    },
    [tree, createMutation, navigateToDocument, toast]
  );

  // Drag and drop - handles both reordering and inserting links
  const handleDragStart = useCallback((event: DragStartEvent) => {
    const id = event.active.id as string;
    setActiveDragId(id);
    // Find the node being dragged
    const node = findNodeById(tree, id);
    setActiveDragNode(node);
  }, [tree]);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragId(null);
    setActiveDragNode(null);

    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    // Check if dropped on the editor drop zone - insert link or embed
    if (overId === "document-editor-drop-zone") {
      const draggedNode = findNodeById(tree, activeId);
      if (draggedNode) {
        // Use shift key to determine embed vs link
        if (isShiftHeld && insertFunctionsRef.current?.insertEmbed) {
          insertFunctionsRef.current.insertEmbed(draggedNode.id, draggedNode.title, draggedNode.icon);
          toast({
            title: "Document embedded",
            description: `Added embed card for "${draggedNode.title}"`,
          });
        } else if (insertFunctionsRef.current?.insertLink || insertLinkRef.current) {
          const insertFn = insertFunctionsRef.current?.insertLink || insertLinkRef.current;
          insertFn?.(draggedNode.id, draggedNode.title, draggedNode.icon);
          toast({
            title: "Link inserted",
            description: `Added inline link to "${draggedNode.title}"`,
          });
        }
      }
      return;
    }

    // Otherwise, handle reordering if dropped on another document
    if (activeId === overId) return;

    const activeContext = getNodeContext(tree, activeId);
    const overContext = getNodeContext(tree, overId);

    if (!activeContext || !overContext) return;

    // If same parent, reorder within siblings
    if (activeContext.parentId === overContext.parentId) {
      const siblings = activeContext.siblings;
      const oldIndex = siblings.findIndex((n) => n.id === activeId);
      const newIndex = siblings.findIndex((n) => n.id === overId);

      // Create updates for all affected siblings
      const updates = siblings.map((sibling, index) => {
        let newOrder = index;
        if (index === oldIndex) {
          newOrder = newIndex;
        } else if (oldIndex < newIndex && index > oldIndex && index <= newIndex) {
          newOrder = index - 1;
        } else if (oldIndex > newIndex && index >= newIndex && index < oldIndex) {
          newOrder = index + 1;
        }
        return {
          id: sibling.id,
          parentId: activeContext.parentId,
          sortOrder: newOrder,
        };
      });

      handleReorder(updates);
    } else {
      // Moving to different parent - place after the over node
      const overIndex = overContext.siblings.findIndex((n) => n.id === overId);

      const updates = [
        {
          id: activeId,
          parentId: overContext.parentId,
          sortOrder: overIndex + 1,
        },
      ];

      // Update sort orders of nodes after insertion point
      overContext.siblings
        .filter((_, i) => i > overIndex)
        .forEach((sibling) => {
          const currentIndex = overContext.siblings.findIndex((n) => n.id === sibling.id);
          updates.push({
            id: sibling.id,
            parentId: overContext.parentId,
            sortOrder: currentIndex + 1,
          });
        });

      handleReorder(updates);
    }
  }, [tree, handleReorder, toast, isShiftHeld]);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="h-full flex flex-col">
        {/* Breadcrumbs bar */}
        <div className="border-b px-4 py-2 bg-muted/30">
          <DocumentBreadcrumbs
            items={breadcrumbs}
            canGoBack={navigationHistory.length > 0}
            onBack={navigateBack}
            onNavigate={navigateToDocument}
            onGoHome={navigateHome}
          />
        </div>

        {/* Main content */}
        <div className="flex-1 min-h-0">
          <ResizablePanelGroup direction="horizontal">
            {/* Sidebar */}
            <ResizablePanel defaultSize={25} minSize={15} maxSize={40}>
              <DocumentSidebar
                nodes={tree}
                isLoading={isTreeLoading}
                selectedId={currentDocumentId}
                onSelect={navigateToDocument}
                onDelete={handleDelete}
                onRename={handleRename}
                onDuplicate={handleDuplicate}
                onCreate={() => setIsCreateDialogOpen(true)}
                canEdit={canEdit}
              />
            </ResizablePanel>

            <ResizableHandle withHandle />

            {/* Document viewer */}
            <ResizablePanel defaultSize={75}>
              <DocumentViewer
                document={currentDocument || null}
                isLoading={isDocLoading}
                onUpdateTitle={handleUpdateTitle}
                onUpdateIcon={handleUpdateIcon}
                onUpdateStatus={handleUpdateStatus}
                onUpdateContent={handleUpdateContent}
                onDelete={() => handleDelete()}
                onNavigate={navigateToDocument}
                canEdit={canEdit}
                onInsertLinkRef={insertLinkRef}
                onInsertFunctionsRef={insertFunctionsRef}
                availableDocuments={flattenedDocuments}
                projectId={projectId}
              />
            </ResizablePanel>
          </ResizablePanelGroup>
        </div>

        {/* Create dialog */}
        <CreateDocumentDialog
          open={isCreateDialogOpen}
          onOpenChange={setIsCreateDialogOpen}
          onSubmit={handleCreate}
          isLoading={createMutation.isPending}
          parentOptions={parentOptions}
        />

        {/* Drag overlay - follows cursor exactly */}
        <DragOverlay modifiers={[snapToCursor]} dropAnimation={null}>
          {activeDragId && activeDragNode && (
            <div className="px-3 py-1.5 bg-background border rounded-md shadow-lg text-sm flex items-center gap-2 pointer-events-none">
              {activeDragNode.icon ? (
                <span>{activeDragNode.icon}</span>
              ) : (
                <span className="text-muted-foreground">📄</span>
              )}
              <span>{activeDragNode.title || "Untitled"}</span>
            </div>
          )}
        </DragOverlay>
      </div>
    </DndContext>
  );
};

export default DocsPanel;
