import { Router, Request, Response, NextFunction } from "express";
import { z } from "zod";
import { requireAuth, loadProjectMembership } from "../auth/middleware";
import { storage } from "../storage";
import {
  isAdmin,
  canAccessFinances,
  canViewProjectFinances,
  canManageProjectFinances,
  canManageBudgets,
  canViewAllFinances,
  canOnlyAddExpenses,
} from "../auth/permissions";
import type { SafeUser, ProjectMember } from "@shared/schema";
import {
  financeQuerySchema,
  budgetQuerySchema,
  insertFinanceTransactionSchema,
  insertProjectBudgetSchema,
} from "@shared/schema";

const router = Router();

// ============================================
// QUERY SCHEMAS
// ============================================

const transactionsQuerySchema = z.object({
  projectId: z.string().optional(),
  year: z.coerce.number().optional(),
  week: z.coerce.number().optional(),
  category: z.enum([
    "programming", "animation", "modeling", "vfx", "sfx",
    "marketing", "video_trailer", "ui", "music", "other"
  ]).optional(),
  currency: z.enum(["robux", "usd"]).optional(),
  type: z.enum(["expense", "income"]).optional(),
  search: z.string().optional(),
  page: z.coerce.number().min(1).optional().default(1),
  limit: z.coerce.number().min(1).max(100).optional().default(50),
});

const createTransactionSchema = z.object({
  projectId: z.string().uuid(),
  type: z.enum(["expense", "income"]).optional().default("expense"),
  category: z.enum([
    "programming", "animation", "modeling", "vfx", "sfx",
    "marketing", "video_trailer", "ui", "music", "other"
  ]),
  currency: z.enum(["robux", "usd"]),
  amount: z.number().int().positive(),
  description: z.string().max(1000).optional(),
  payeeName: z.string().max(200).optional(),
  paymentMethod: z.enum(["robux_direct", "bank_transfer", "paypal", "other"]).optional().default("other"),
  weekNumber: z.number().int().min(1).max(53),
  year: z.number().int().min(2020).max(2100),
  transactionDate: z.string().datetime().optional(),
  receiptUrl: z.string().url().optional(),
  receiptThumbnail: z.string().url().optional(),
});

const updateTransactionSchema = createTransactionSchema.partial().omit({ projectId: true });

const setBudgetSchema = z.object({
  category: z.enum([
    "programming", "animation", "modeling", "vfx", "sfx",
    "marketing", "video_trailer", "ui", "music", "other"
  ]),
  currency: z.enum(["robux", "usd"]),
  budgetAmount: z.number().int().nonnegative(),
  alertThreshold: z.number().int().min(1).max(100).optional().default(80),
  weekNumber: z.number().int().min(1).max(53).optional(),
  year: z.number().int().min(2020).max(2100).optional(),
});

// ============================================
// TRANSACTION ROUTES
// ============================================

/**
 * GET /api/finances
 * List all transactions with optional filtering
 * STRICT PERMISSIONS:
 * - Admins: See all transactions across all projects
 * - Project managers: See transactions for their projects only
 */
router.get("/", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;

    // Check if user can access finances at all
    if (!canAccessFinances(user)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view finances. Only project managers and above can access this.",
        },
      });
    }

    const query = transactionsQuerySchema.safeParse(req.query);

    if (!query.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid query parameters",
          details: query.error.errors,
        },
      });
    }

    const { projectId, year, week, category, currency, type, search, page, limit } = query.data;

    // Get projects where user has finance view permission
    let allowedProjectIds: string[] | undefined = undefined;

    if (!isAdmin(user)) {
      // Get all user's project memberships
      const userProjects = await storage.getUserProjects(user.id);

      // Filter to projects where user can view finances
      allowedProjectIds = [];
      for (const project of userProjects) {
        const membership = await storage.getProjectMember(project.id, user.id);
        if (canViewProjectFinances(user, membership)) {
          allowedProjectIds.push(project.id);
        }
      }

      // If no projects with access, return empty
      if (allowedProjectIds.length === 0) {
        return res.json({
          success: true,
          data: [],
          meta: { total: 0, page, limit, hasMore: false },
        });
      }
    }

    // If specific project is requested, verify access
    if (projectId && !isAdmin(user)) {
      if (!allowedProjectIds?.includes(projectId)) {
        return res.status(403).json({
          success: false,
          error: {
            code: "FORBIDDEN",
            message: "You do not have permission to view finances for this project",
          },
        });
      }
    }

    const result = await storage.getFinanceTransactions({
      projectId,
      projectIds: projectId ? undefined : allowedProjectIds,
      year,
      weekNumber: week,
      category,
      currency,
      type,
      search,
      page,
      limit,
    });

    res.json({
      success: true,
      data: result.transactions,
      meta: {
        total: result.total,
        page,
        limit,
        hasMore: page * limit < result.total,
      },
    });
  } catch (error) {
    next(error);
  }
});

/**
 * GET /api/finances/project/:projectId
 * Get all finance transactions for a specific project
 */
router.get("/project/:projectId", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canViewProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view finances for this project",
        },
      });
    }

    const query = transactionsQuerySchema.safeParse(req.query);
    if (!query.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid query parameters",
          details: query.error.errors,
        },
      });
    }

    const transactions = await storage.getProjectFinanceTransactions(projectId, {
      year: query.data.year,
      weekNumber: query.data.week,
      category: query.data.category,
      currency: query.data.currency,
      type: query.data.type,
    });

    res.json({
      success: true,
      data: transactions,
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/finances/transaction
 * Create a new finance transaction
 */
router.post("/transaction", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;

    const parsed = createTransactionSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid transaction data",
          details: parsed.error.errors,
        },
      });
    }

    const data = parsed.data;

    // Check project access
    const project = await storage.getProject(data.projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(data.projectId, user.id);
    if (!canManageProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to add transactions to this project",
        },
      });
    }

    // Project managers can only add expenses, not income
    if (canOnlyAddExpenses(user, membership) && data.type === "income") {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Project managers can only add expense transactions. Only project owners and admins can add income.",
        },
      });
    }

    const transaction = await storage.createFinanceTransaction(
      {
        ...data,
        description: data.description ?? "",
        transactionDate: data.transactionDate ? new Date(data.transactionDate) : new Date(),
      },
      user.id
    );

    res.status(201).json({
      success: true,
      data: transaction,
      message: "Transaction created successfully",
    });
  } catch (error) {
    next(error);
  }
});

/**
 * PATCH /api/finances/transaction/:id
 * Update a finance transaction
 */
router.patch("/transaction/:id", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { id } = req.params;

    const transaction = await storage.getFinanceTransaction(id);
    if (!transaction) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Transaction not found" },
      });
    }

    // Check permissions - creator or manager can update
    const membership = await storage.getProjectMember(transaction.projectId, user.id);
    const isCreator = transaction.createdById === user.id;
    const canManage = canManageProjectFinances(user, membership);

    if (!isCreator && !canManage) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to update this transaction",
        },
      });
    }

    // Project managers cannot edit income transactions at all
    if (canOnlyAddExpenses(user, membership) && transaction.type === "income") {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Project managers cannot edit income transactions. Only project owners and admins can manage income.",
        },
      });
    }

    const parsed = updateTransactionSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid update data",
          details: parsed.error.errors,
        },
      });
    }

    // Also prevent changing expense to income
    if (canOnlyAddExpenses(user, membership) && parsed.data.type === "income") {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Project managers can only create expense transactions. Only project owners and admins can create income.",
        },
      });
    }

    const updated = await storage.updateFinanceTransaction(id, {
      ...parsed.data,
      transactionDate: parsed.data.transactionDate ? new Date(parsed.data.transactionDate) : undefined,
      updatedAt: new Date(),
    });

    res.json({
      success: true,
      data: updated,
      message: "Transaction updated successfully",
    });
  } catch (error) {
    next(error);
  }
});

/**
 * DELETE /api/finances/transaction/:id
 * Delete a finance transaction (soft delete)
 */
router.delete("/transaction/:id", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { id } = req.params;

    const transaction = await storage.getFinanceTransaction(id);
    if (!transaction) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Transaction not found" },
      });
    }

    // Check permissions - creator or manager can delete
    const membership = await storage.getProjectMember(transaction.projectId, user.id);
    const isCreator = transaction.createdById === user.id;
    const canManage = canManageProjectFinances(user, membership);

    if (!isCreator && !canManage) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to delete this transaction",
        },
      });
    }

    // Project managers cannot delete income transactions
    if (canOnlyAddExpenses(user, membership) && transaction.type === "income") {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Project managers cannot delete income transactions. Only project owners and admins can manage income.",
        },
      });
    }

    await storage.deleteFinanceTransaction(id);

    res.json({
      success: true,
      message: "Transaction deleted successfully",
    });
  } catch (error) {
    next(error);
  }
});

// ============================================
// BUDGET ROUTES
// ============================================

/**
 * GET /api/finances/project/:projectId/budgets
 * Get all budgets for a project
 */
router.get("/project/:projectId/budgets", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canViewProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view budgets for this project",
        },
      });
    }

    const query = z.object({
      year: z.coerce.number().optional(),
      week: z.coerce.number().optional(),
    }).safeParse(req.query);

    const budgets = await storage.getProjectBudgets(projectId, {
      year: query.success ? query.data.year : undefined,
      weekNumber: query.success ? query.data.week : undefined,
    });

    res.json({
      success: true,
      data: budgets,
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/finances/project/:projectId/budget
 * Create or update a budget for a project
 */
router.post("/project/:projectId/budget", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canManageBudgets(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Only project owners and admins can set budgets",
        },
      });
    }

    const parsed = setBudgetSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid budget data",
          details: parsed.error.errors,
        },
      });
    }

    const budget = await storage.upsertProjectBudget(
      {
        projectId,
        ...parsed.data,
      },
      user.id
    );

    res.status(201).json({
      success: true,
      data: budget,
      message: "Budget saved successfully",
    });
  } catch (error) {
    next(error);
  }
});

/**
 * DELETE /api/finances/budget/:id
 * Delete a budget
 */
router.delete("/budget/:id", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { id } = req.params;

    // Need to get the budget first to check project permissions
    // For now, only admins can delete budgets directly
    if (!isAdmin(user)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Only admins can delete budgets",
        },
      });
    }

    await storage.deleteProjectBudget(id);

    res.json({
      success: true,
      message: "Budget deleted successfully",
    });
  } catch (error) {
    next(error);
  }
});

// ============================================
// SUMMARY/ANALYTICS ROUTES
// ============================================

/**
 * GET /api/finances/project/:projectId/summary
 * Get finance summary for a project (for pie charts and stats)
 */
router.get("/project/:projectId/summary", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canViewProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view finances for this project",
        },
      });
    }

    const query = z.object({
      year: z.coerce.number().optional(),
      week: z.coerce.number().optional(),
    }).safeParse(req.query);

    const summary = await storage.getProjectFinanceSummary(projectId, {
      year: query.success ? query.data.year : undefined,
      weekNumber: query.success ? query.data.week : undefined,
    });

    res.json({
      success: true,
      data: summary,
    });
  } catch (error) {
    next(error);
  }
});

/**
 * GET /api/finances/project/:projectId/spending
 * Get category spending breakdown for a project
 */
router.get("/project/:projectId/spending", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canViewProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view finances for this project",
        },
      });
    }

    const query = z.object({
      year: z.coerce.number().optional(),
      week: z.coerce.number().optional(),
    }).safeParse(req.query);

    const spending = await storage.getCategorySpending(projectId, {
      year: query.success ? query.data.year : undefined,
      weekNumber: query.success ? query.data.week : undefined,
    });

    res.json({
      success: true,
      data: spending,
    });
  } catch (error) {
    next(error);
  }
});

/**
 * GET /api/finances/project/:projectId/budgets-with-spending
 * Get budgets with their spending data (for budget progress bars)
 */
router.get("/project/:projectId/budgets-with-spending", requireAuth, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = req.user as SafeUser;
    const { projectId } = req.params;

    // Check project access
    const project = await storage.getProject(projectId);
    if (!project) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Project not found" },
      });
    }

    const membership = await storage.getProjectMember(projectId, user.id);
    if (!canViewProjectFinances(user, membership)) {
      return res.status(403).json({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "You do not have permission to view finances for this project",
        },
      });
    }

    const budgetsWithSpending = await storage.getBudgetsWithSpending(projectId);

    res.json({
      success: true,
      data: budgetsWithSpending,
    });
  } catch (error) {
    next(error);
  }
});

export default router;
