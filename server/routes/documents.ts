import { Router } from "express";
import { z } from "zod";
import { storage } from "../storage";
import { requireAuth, loadProjectMembership } from "../auth/middleware";
import { canViewProject, canManageProject } from "../auth/permissions";
import {
  insertDocumentSchema,
  updateDocumentSchema,
  type SafeUser,
  type TipTapDocument,
  type TipTapNode,
} from "@shared/schema";

const router = Router({ mergeParams: true });

// Helper function to extract document link IDs from TipTap content
// Includes both inline links and inline embeds
function extractDocumentLinkIds(content: TipTapDocument | null): string[] {
  if (!content || !content.content) return [];

  const linkIds: string[] = [];

  const traverse = (nodes: TipTapNode[]) => {
    for (const node of nodes) {
      // Include both documentLink and inlineDocumentEmbed nodes
      if (
        (node.type === "documentLink" || node.type === "inlineDocumentEmbed") &&
        node.attrs?.documentId
      ) {
        linkIds.push(node.attrs.documentId as string);
      }
      if (node.content) {
        traverse(node.content);
      }
    }
  };

  traverse(content.content);
  return [...new Set(linkIds)]; // Remove duplicates
}

// Helper function to extract plain text from TipTap content
function extractPlainText(content: TipTapDocument | null): string {
  if (!content || !content.content) return "";

  const textParts: string[] = [];

  const traverse = (nodes: TipTapNode[]) => {
    for (const node of nodes) {
      if (node.text) {
        textParts.push(node.text);
      }
      if (node.content) {
        traverse(node.content);
      }
    }
  };

  traverse(content.content);
  return textParts.join(" ");
}

/**
 * GET /api/projects/:projectId/documents
 * List all documents for a project (flat list with metadata)
 */
router.get(
  "/",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canViewProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const documents = await storage.getProjectDocuments(req.params.projectId);
      res.json({ success: true, data: documents });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/projects/:projectId/documents/tree
 * Get document tree structure for the sidebar
 */
router.get(
  "/tree",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canViewProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const tree = await storage.getDocumentTree(req.params.projectId);
      res.json({ success: true, data: tree });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/projects/:projectId/documents/:id
 * Get a single document with content and backlinks
 */
router.get(
  "/:id",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canViewProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const document = await storage.getDocumentWithLinks(req.params.id);

      if (!document) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      // Verify document belongs to the project
      if (document.projectId !== req.params.projectId) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      res.json({ success: true, data: document });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * POST /api/projects/:projectId/documents
 * Create a new document
 */
router.post(
  "/",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canManageProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const data = insertDocumentSchema.parse({
        ...req.body,
        projectId: req.params.projectId,
      });

      const document = await storage.createDocument(data, user.id);

      // Log activity
      await storage.logActivity({
        projectId: req.params.projectId,
        userId: user.id,
        type: "reference_added", // Using existing type for now
        message: `Created document "${document.title}"`,
        metadata: { documentId: document.id },
      });

      res.status(201).json({ success: true, data: document });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({
          success: false,
          error: {
            code: "VALIDATION_ERROR",
            message: "Invalid request data",
            details: error.errors,
          },
        });
      }
      next(error);
    }
  }
);

/**
 * PATCH /api/projects/:projectId/documents/:id
 * Update a document
 */
router.patch(
  "/:id",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canManageProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      // Verify document exists and belongs to project
      const existingDoc = await storage.getDocument(req.params.id);
      if (!existingDoc || existingDoc.projectId !== req.params.projectId) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      const data = updateDocumentSchema.parse(req.body);

      // Extract plain text for search if content is being updated
      let contentText: string | undefined;
      if (data.content) {
        contentText = extractPlainText(data.content as TipTapDocument);
      }

      const document = await storage.updateDocument(
        req.params.id,
        { ...data, contentText },
        user.id
      );

      // Sync document links if content was updated
      if (data.content) {
        const linkIds = extractDocumentLinkIds(data.content as TipTapDocument);
        await storage.syncDocumentLinks(req.params.id, linkIds);
      }

      res.json({ success: true, data: document });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({
          success: false,
          error: {
            code: "VALIDATION_ERROR",
            message: "Invalid request data",
            details: error.errors,
          },
        });
      }
      next(error);
    }
  }
);

/**
 * DELETE /api/projects/:projectId/documents/:id
 * Soft delete a document
 */
router.delete(
  "/:id",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canManageProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      // Verify document exists and belongs to project
      const existingDoc = await storage.getDocument(req.params.id);
      if (!existingDoc || existingDoc.projectId !== req.params.projectId) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      await storage.deleteDocument(req.params.id);

      res.json({ success: true, message: "Document deleted" });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/projects/:projectId/documents/:id/backlinks
 * Get documents that link to this document
 */
router.get(
  "/:id/backlinks",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canViewProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const backlinks = await storage.getDocumentBacklinks(req.params.id);
      res.json({ success: true, data: backlinks });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * GET /api/projects/:projectId/documents/:id/embed
 * Get lightweight document data for embedding (no backlinks, no user data)
 */
router.get(
  "/:id/embed",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canViewProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const document = await storage.getDocument(req.params.id);

      if (!document) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      // Verify document belongs to the project
      if (document.projectId !== req.params.projectId) {
        return res.status(404).json({
          success: false,
          error: { code: "NOT_FOUND", message: "Document not found" },
        });
      }

      // Return lightweight embed response
      res.json({
        success: true,
        data: {
          id: document.id,
          title: document.title,
          icon: document.icon,
          content: document.content,
          updatedAt: document.updatedAt,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

/**
 * PATCH /api/projects/:projectId/documents/reorder
 * Reorder documents (update parentId and sortOrder)
 */
router.patch(
  "/reorder",
  requireAuth,
  loadProjectMembership("projectId"),
  async (req, res, next) => {
    try {
      const user = req.user as SafeUser;
      const membership = (req as any).projectMembership;

      if (!canManageProject(user, membership)) {
        return res.status(403).json({
          success: false,
          error: { code: "FORBIDDEN", message: "Access denied" },
        });
      }

      const reorderSchema = z.object({
        updates: z.array(
          z.object({
            id: z.string(),
            parentId: z.string().nullable(),
            sortOrder: z.number(),
          })
        ),
      });

      const { updates } = reorderSchema.parse(req.body);

      await storage.reorderDocuments(req.params.projectId, updates);

      res.json({ success: true, message: "Documents reordered" });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({
          success: false,
          error: {
            code: "VALIDATION_ERROR",
            message: "Invalid request data",
            details: error.errors,
          },
        });
      }
      next(error);
    }
  }
);

export default router;
