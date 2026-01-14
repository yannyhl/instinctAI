import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  Document,
  DocumentWithMeta,
  DocumentTreeNode,
  DocumentWithLinks,
  InsertDocument,
  TipTapDocument,
  EmbeddedDocumentResponse,
} from "@shared/schema";

const API_BASE = "/api/projects";

// ============================================
// QUERY HOOKS
// ============================================

/**
 * Fetch all documents for a project (flat list with metadata)
 */
export function useProjectDocuments(projectId: string | undefined) {
  return useQuery<DocumentWithMeta[]>({
    queryKey: ["documents", projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const res = await fetch(`${API_BASE}/${projectId}/documents`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch documents");
      const data = await res.json();
      return data.data;
    },
    enabled: !!projectId,
  });
}

/**
 * Fetch document tree structure for the sidebar
 */
export function useDocumentTree(projectId: string | undefined) {
  return useQuery<DocumentTreeNode[]>({
    queryKey: ["documents", projectId, "tree"],
    queryFn: async () => {
      if (!projectId) return [];
      const res = await fetch(`${API_BASE}/${projectId}/documents/tree`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch document tree");
      const data = await res.json();
      return data.data;
    },
    enabled: !!projectId,
  });
}

/**
 * Fetch a single document with content and backlinks
 */
export function useDocument(projectId: string | undefined, documentId: string | undefined) {
  return useQuery<DocumentWithLinks>({
    queryKey: ["documents", projectId, documentId],
    queryFn: async () => {
      if (!projectId || !documentId) throw new Error("Missing IDs");
      const res = await fetch(`${API_BASE}/${projectId}/documents/${documentId}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch document");
      const data = await res.json();
      return data.data;
    },
    enabled: !!projectId && !!documentId,
  });
}

/**
 * Fetch backlinks for a document
 */
export function useDocumentBacklinks(projectId: string | undefined, documentId: string | undefined) {
  return useQuery<{ id: string; title: string; icon: string | null }[]>({
    queryKey: ["documents", projectId, documentId, "backlinks"],
    queryFn: async () => {
      if (!projectId || !documentId) return [];
      const res = await fetch(`${API_BASE}/${projectId}/documents/${documentId}/backlinks`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch backlinks");
      const data = await res.json();
      return data.data;
    },
    enabled: !!projectId && !!documentId,
  });
}

/**
 * Fetch lightweight document data for embedding (no backlinks)
 * Uses longer cache times since embedded content changes less frequently
 */
export function useEmbeddedDocument(projectId: string | undefined, documentId: string | undefined) {
  return useQuery<EmbeddedDocumentResponse>({
    queryKey: ["documents", projectId, documentId, "embed"],
    queryFn: async () => {
      if (!projectId || !documentId) throw new Error("Missing IDs");
      const res = await fetch(`${API_BASE}/${projectId}/documents/${documentId}/embed`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch embedded document");
      const data = await res.json();
      return data.data;
    },
    enabled: !!projectId && !!documentId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

// ============================================
// MUTATION HOOKS
// ============================================

/**
 * Create a new document
 */
export function useCreateDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Omit<InsertDocument, "projectId">) => {
      const res = await fetch(`${API_BASE}/${projectId}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error?.message || "Failed to create document");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

/**
 * Update a document
 */
export function useUpdateDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: Partial<{
        title: string;
        content: TipTapDocument;
        icon: string | null;
        status: "draft" | "published" | "archived";
        parentId: string | null;
      }>;
    }) => {
      const res = await fetch(`${API_BASE}/${projectId}/documents/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error?.message || "Failed to update document");
      }
      return res.json();
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      queryClient.invalidateQueries({ queryKey: ["documents", projectId, variables.id] });
      // Also invalidate embed cache for this document
      queryClient.invalidateQueries({ queryKey: ["documents", projectId, variables.id, "embed"] });
    },
  });
}

/**
 * Delete a document
 */
export function useDeleteDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      const res = await fetch(`${API_BASE}/${projectId}/documents/${documentId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error?.message || "Failed to delete document");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

/**
 * Reorder documents (update parent and sort order)
 */
export function useReorderDocuments(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      updates: { id: string; parentId: string | null; sortOrder: number }[]
    ) => {
      const res = await fetch(`${API_BASE}/${projectId}/documents/reorder`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ updates }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error?.message || "Failed to reorder documents");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

// ============================================
// UTILITY TYPES
// ============================================

export type { Document, DocumentWithMeta, DocumentTreeNode, DocumentWithLinks };
