import type { SafeUser, ProjectMember, OrgRole, ProjectRole } from "@shared/schema";

// ============================================
// ROLE HIERARCHY
// ============================================

export const ORG_ROLE_LEVELS: Record<OrgRole, number> = {
  ceo: 100,
  cto: 95,
  coo: 95,
  director: 80,
  project_manager: 70,
  lead: 60,
  senior: 50,
  member: 40,
  contractor: 10,
};

export const PROJECT_ROLE_LEVELS: Record<ProjectRole, number> = {
  owner: 100,
  manager: 80,
  contributor: 50,
  viewer: 10,
};

// ============================================
// PERMISSION DEFINITIONS
// ============================================

export const PERMISSIONS = {
  // Project-level permissions
  canManageProject: "canManageProject", // create/edit/delete projects
  canManageTeam: "canManageTeam", // add/remove members, assign roles
  canAssignTasks: "canAssignTasks", // assign tasks to team members
  canEditOwnTasks: "canEditOwnTasks", // edit tasks assigned to self
  canUploadFiles: "canUploadFiles", // upload attachments
  canViewProject: "canViewProject", // read access to project
  canDeleteTasks: "canDeleteTasks", // delete tasks
  canReassignTasks: "canReassignTasks", // reassign tasks to others
  canAccessSettings: "canAccessSettings", // access management settings
  canCreateReleases: "canCreateReleases", // create release cycles
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

// ============================================
// ROLE-BASED PERMISSION MATRIX
// ============================================

const ORG_ROLE_PERMISSIONS: Record<OrgRole, Permission[]> = {
  ceo: Object.values(PERMISSIONS),
  cto: Object.values(PERMISSIONS),
  coo: Object.values(PERMISSIONS),
  director: Object.values(PERMISSIONS),
  project_manager: [
    PERMISSIONS.canManageProject,
    PERMISSIONS.canManageTeam,
    PERMISSIONS.canAssignTasks,
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
    PERMISSIONS.canDeleteTasks,
    PERMISSIONS.canReassignTasks,
    PERMISSIONS.canAccessSettings,
    PERMISSIONS.canCreateReleases,
  ],
  lead: [
    PERMISSIONS.canManageTeam,
    PERMISSIONS.canAssignTasks,
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
    PERMISSIONS.canReassignTasks,
  ],
  senior: [
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
  ],
  member: [
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
  ],
  contractor: [PERMISSIONS.canViewProject],
};

const PROJECT_ROLE_PERMISSIONS: Record<ProjectRole, Permission[]> = {
  owner: Object.values(PERMISSIONS),
  manager: [
    PERMISSIONS.canManageProject,
    PERMISSIONS.canManageTeam,
    PERMISSIONS.canAssignTasks,
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
    PERMISSIONS.canDeleteTasks,
    PERMISSIONS.canReassignTasks,
    PERMISSIONS.canAccessSettings,
    PERMISSIONS.canCreateReleases,
  ],
  contributor: [
    PERMISSIONS.canEditOwnTasks,
    PERMISSIONS.canUploadFiles,
    PERMISSIONS.canViewProject,
  ],
  viewer: [PERMISSIONS.canViewProject],
};

// ============================================
// PERMISSION CHECKING UTILITIES
// ============================================

interface PermissionContext {
  user: SafeUser;
  projectMembership?: ProjectMember | null;
  taskAssigneeId?: string;
}

/**
 * Check if user has a specific permission in context
 */
export function hasPermission(
  permission: Permission,
  context: PermissionContext
): boolean {
  const { user, projectMembership, taskAssigneeId } = context;

  // Admin/Director+ always have full access
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.director) {
    return true;
  }

  // Get org-level permissions
  const orgPermissions = ORG_ROLE_PERMISSIONS[user.orgRole] || [];

  // If no project context, only check org permissions
  if (!projectMembership) {
    return orgPermissions.includes(permission);
  }

  // Get project role permissions
  const projectPermissions =
    PROJECT_ROLE_PERMISSIONS[projectMembership.projectRole] || [];

  // Combine permissions - project role can grant additional permissions
  const allPermissions = new Set([...orgPermissions, ...projectPermissions]);

  // Special case: Contractors can only update their own task status
  if (
    user.orgRole === "contractor" &&
    permission === PERMISSIONS.canEditOwnTasks
  ) {
    return taskAssigneeId === user.id;
  }

  return allPermissions.has(permission);
}

/**
 * Check if user can manage a specific project
 */
export function canManageProject(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canManageProject, {
    user,
    projectMembership,
  });
}

/**
 * Check if user can manage team members
 */
export function canManageTeam(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canManageTeam, { user, projectMembership });
}

/**
 * Check if user can assign tasks
 */
export function canAssignTasks(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canAssignTasks, { user, projectMembership });
}

/**
 * Check if user can edit a specific task
 * Key permission: members can only edit tasks assigned to them
 */
export function canEditTask(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined,
  taskAssigneeId?: string | null
): boolean {
  // Admin/Director can edit any task
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.director) {
    return true;
  }

  // Project managers and owners can edit any task in their project
  if (
    projectMembership?.projectRole === "owner" ||
    projectMembership?.projectRole === "manager"
  ) {
    return true;
  }

  // Others can only edit tasks assigned to them
  if (taskAssigneeId && taskAssigneeId === user.id) {
    return hasPermission(PERMISSIONS.canEditOwnTasks, {
      user,
      projectMembership,
      taskAssigneeId,
    });
  }

  return false;
}

/**
 * Check if user can upload files
 */
export function canUploadFiles(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  // Contractors cannot upload files
  if (user.orgRole === "contractor") {
    return false;
  }
  return hasPermission(PERMISSIONS.canUploadFiles, { user, projectMembership });
}

/**
 * Check if user can view project
 * Note: This is a synchronous permission check. For task assignment-based access,
 * use canViewProjectWithTasks() which checks the database for assignments.
 */
export function canViewProject(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canViewProject, { user, projectMembership });
}

/**
 * Check if user can view project (async version with task assignment check)
 * Returns true if:
 * - User has normal project viewing permissions, OR
 * - User has any tasks/subtasks assigned to them in this project
 *
 * This enables task assignees to access the project even without formal membership.
 */
export async function canViewProjectWithTasks(
  user: SafeUser,
  projectId: string,
  projectMembership?: ProjectMember | null
): Promise<boolean> {
  // Check standard permissions first
  if (canViewProject(user, projectMembership)) {
    return true;
  }

  // If standard permissions fail, check if user has any assigned tasks in this project
  // This requires database access, so we import storage dynamically
  try {
    const { storage } = await import("../storage");
    const hasAssignedTasks = await storage.userHasAssignedTasksInProject(projectId, user.id);
    return hasAssignedTasks;
  } catch (error) {
    console.error("[Permissions] Error checking task assignments:", error);
    return false;
  }
}

/**
 * Check if user can create new projects
 * Only project_manager and above can create projects
 */
export function canCreateProjects(user: SafeUser): boolean {
  return ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.project_manager;
}

/**
 * Check if user is an admin (C-Suite/Director)
 * Admins have full access to all resources
 */
export function isAdmin(user: SafeUser): boolean {
  return ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.director;
}

/**
 * Check if user can access settings
 */
export function canAccessSettings(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canAccessSettings, {
    user,
    projectMembership,
  });
}

/**
 * Check if user can create releases
 */
export function canCreateReleases(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): boolean {
  return hasPermission(PERMISSIONS.canCreateReleases, {
    user,
    projectMembership,
  });
}

/**
 * Get effective role level (higher of org or project)
 */
export function getEffectiveRoleLevel(
  user: SafeUser,
  projectMembership?: ProjectMember | null
): number {
  const orgLevel = ORG_ROLE_LEVELS[user.orgRole] || 0;

  if (!projectMembership) {
    return orgLevel;
  }

  const projectLevel =
    PROJECT_ROLE_LEVELS[projectMembership.projectRole] || 0;

  // Scale project level to comparable range (max 80 = director level)
  const normalizedProjectLevel = (projectLevel / 100) * 80;

  return Math.max(orgLevel, normalizedProjectLevel);
}

/**
 * Check if user has at least the specified org role level
 */
export function hasMinOrgRole(user: SafeUser, minRole: OrgRole): boolean {
  return ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS[minRole];
}

/**
 * Check if user has at least the specified project role level
 */
export function hasMinProjectRole(
  projectMembership: ProjectMember | null | undefined,
  minRole: ProjectRole
): boolean {
  if (!projectMembership) return false;
  return (
    PROJECT_ROLE_LEVELS[projectMembership.projectRole] >=
    PROJECT_ROLE_LEVELS[minRole]
  );
}

/**
 * Check if user can view assets for a project
 * STRICT PERMISSIONS:
 * - C-Suite/Admin: Can see all assets
 * - Project managers/owners (project role): Can see their project's assets
 * - Programmers (job role) assigned to project: Can see project assets
 * - Everyone else: NO access to assets
 */
export function canViewProjectAssets(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // C-Suite/Admin can see all assets
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Project managers/owners can view assets
  if (PROJECT_ROLE_LEVELS[projectMembership.projectRole] >= PROJECT_ROLE_LEVELS.manager) {
    return true;
  }

  // Programmers assigned to the project can view assets
  if (user.jobRole === 'programmer') return true;

  // Everyone else - NO access
  return false;
}

/**
 * Check if user can access the Assets section at all
 * Returns true if user is admin, programmer, or org-level project manager+
 */
export function canAccessAssets(user: SafeUser): boolean {
  // Admins can access
  if (isAdmin(user)) return true;

  // Programmers can access
  if (user.jobRole === 'programmer') return true;

  // Org-level project managers and above can access
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.project_manager) return true;

  // Everyone else - no access
  return false;
}

/**
 * Check if user can upload assets to a project
 * PERMISSIONS:
 * - C-Suite/Admin: Can upload to any project
 * - Project managers/owners (project role): Can upload to their projects
 * - Programmers (job role) assigned to project: Can upload
 * - Contributors/Members with contributor+ project role: Can upload for their assigned tasks
 * - Viewers/Contractors: NO upload access
 */
export function canUploadAsset(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Contractors cannot upload
  if (user.orgRole === "contractor") return false;

  // C-Suite/Admin can upload to any project
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Contributors and above can upload (for their assigned tasks)
  if (PROJECT_ROLE_LEVELS[projectMembership.projectRole] >= PROJECT_ROLE_LEVELS.contributor) {
    return true;
  }

  // Viewers cannot upload
  return false;
}

/**
 * Check if user can delete assets from a project
 * STRICT PERMISSIONS:
 * - C-Suite/Admin: Can delete any asset
 * - Project managers/owners: Can delete any asset in their project
 * - Programmers: Can delete their own uploads only
 */
export function canDeleteAsset(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined,
  assetUploaderId?: string
): boolean {
  // C-Suite/Admin can delete any asset
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Project managers/owners can delete any asset in their project
  if (PROJECT_ROLE_LEVELS[projectMembership.projectRole] >= PROJECT_ROLE_LEVELS.manager) {
    return true;
  }

  // Programmers can delete their own uploads
  if (user.jobRole === "programmer" && assetUploaderId === user.id) return true;

  // Everyone else - NO delete access
  return false;
}

// ============================================
// FINANCE PERMISSIONS
// ============================================

/**
 * Check if user can access the Finances section at all
 * Returns true if user is admin or org-level project manager+
 */
export function canAccessFinances(user: SafeUser): boolean {
  // Admins can access all finances
  if (isAdmin(user)) return true;

  // Org-level project managers and above can access
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.project_manager) return true;

  // Everyone else - no access
  return false;
}

/**
 * Check if user can view finance data for a specific project
 * - Admins: Can view all projects
 * - Project managers/owners (project role): Can view their project's finances
 */
export function canViewProjectFinances(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Admins can view all finances
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Project managers/owners can view finances
  if (PROJECT_ROLE_LEVELS[projectMembership.projectRole] >= PROJECT_ROLE_LEVELS.manager) {
    return true;
  }

  // Org-level project managers viewing their assigned projects
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.project_manager) {
    return true;
  }

  // Everyone else - NO access
  return false;
}

/**
 * Check if user can create/edit/delete transactions for a project
 * Same as canViewProjectFinances - managers+ can manage
 */
export function canManageProjectFinances(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  return canViewProjectFinances(user, projectMembership);
}

/**
 * Check if user can set/modify budgets for a project
 * More restrictive - only project owners and admins
 */
export function canManageBudgets(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Admins can manage all budgets
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Only project owners can set budgets
  if (projectMembership.projectRole === "owner") {
    return true;
  }

  // Everyone else - NO access to budget management
  return false;
}

/**
 * Check if user can only add expense transactions (not income)
 * Project managers can add expenses but not income
 * Only admins and project owners can add income
 */
export function canOnlyAddExpenses(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Admins can add both income and expenses
  if (isAdmin(user)) return false;

  // Project owners can add both income and expenses
  if (projectMembership?.projectRole === "owner") return false;

  // Everyone else (including project managers) can only add expenses
  return true;
}

/**
 * Check if user can view all projects' finances (admin-only feature)
 */
export function canViewAllFinances(user: SafeUser): boolean {
  return isAdmin(user);
}

// ============================================
// GAME REVENUE ANALYTICS PERMISSIONS
// ============================================

/**
 * Check if user can view game revenue data
 * Reuses existing finance permissions since games are financial data
 */
export function canViewGameRevenue(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  return canViewProjectFinances(user, projectMembership);
}

/**
 * Check if user can manage games (create/edit/delete)
 * Reuses existing finance management permissions
 */
export function canManageGames(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  return canManageProjectFinances(user, projectMembership);
}

/**
 * Check if user can manage revenue shares for a game
 * More restrictive - only project owners and admins
 * Revenue shares represent ownership stakes and are highly sensitive
 */
export function canManageRevenueShares(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Admins can manage all revenue shares
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Only project owners can manage revenue shares
  return projectMembership.projectRole === "owner";
}

// ============================================
// TASK VISIBILITY PERMISSIONS
// ============================================

/**
 * Check if user can view ALL tasks in a project (not just assigned ones)
 * PERMISSIONS:
 * - C-Suite/Admin: Can see all tasks
 * - Project managers/owners (project role): Can see all tasks
 * - Contractors (org role): Can ONLY see tasks assigned to them (regardless of project role)
 * - Viewers (project role): Can ONLY see tasks assigned to them
 * - Lead/Senior/Member (org role) with contributor+ project role: Can see all tasks
 */
export function canViewAllTasks(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  // Admins can see all tasks
  if (isAdmin(user)) return true;

  // Must be a project member
  if (!projectMembership) return false;

  // Project managers/owners can see all tasks
  if (PROJECT_ROLE_LEVELS[projectMembership.projectRole] >= PROJECT_ROLE_LEVELS.manager) {
    return true;
  }

  // CRITICAL: Check contractor org role BEFORE contributor project role
  // Contractors can ONLY see their assigned tasks, even if they have "contributor" project role
  if (user.orgRole === "contractor") {
    return false;
  }

  // Viewers can only see their assigned tasks
  if (projectMembership.projectRole === "viewer") {
    return false;
  }

  // Regular employees (non-contractors) with contributor role can see all tasks
  if (projectMembership.projectRole === "contributor") {
    return true;
  }

  // Lead/Senior org roles can see all tasks in their projects
  if (ORG_ROLE_LEVELS[user.orgRole] >= ORG_ROLE_LEVELS.senior) {
    return true;
  }

  // Default: members can see all tasks
  return true;
}

/**
 * Check if user can view a specific task
 * - If canViewAllTasks is true, they can view any task
 * - Otherwise, they can only view tasks assigned to them
 */
export function canViewTask(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined,
  taskAssigneeId: string | null | undefined
): boolean {
  // If user can view all tasks, allow
  if (canViewAllTasks(user, projectMembership)) {
    return true;
  }

  // Otherwise, only allow if task is assigned to them
  return taskAssigneeId === user.id;
}

/**
 * Check if user should have tasks filtered to only assigned ones
 * Returns true if we should filter, false if they can see all
 */
export function shouldFilterTasksByAssignee(
  user: SafeUser,
  projectMembership: ProjectMember | null | undefined
): boolean {
  return !canViewAllTasks(user, projectMembership);
}
