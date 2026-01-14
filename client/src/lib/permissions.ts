/**
 * Permission utilities for role-based access control
 *
 * Org Role Hierarchy (highest to lowest):
 * - ceo (100)
 * - cto (95)
 * - coo (95)
 * - director (80)
 * - project_manager (70)
 * - lead (60)
 * - senior (50)
 * - member (40)
 * - contractor (10)
 *
 * Project Role Hierarchy:
 * - owner (100)
 * - manager (80)
 * - contributor (50)
 * - viewer (10)
 */

import type { User } from '@/contexts/AuthContext';

// Org role levels - higher number = more permissions
export const ORG_ROLE_LEVELS: Record<string, number> = {
  ceo: 100,
  cto: 95,
  coo: 95,  // Same as CTO - C-Suite level
  director: 80,
  project_manager: 70,
  lead: 60,
  senior: 50,
  member: 40,
  contractor: 10,
};

// Project role levels
export const PROJECT_ROLE_LEVELS: Record<string, number> = {
  owner: 100,
  manager: 80,
  contributor: 50,
  viewer: 10,
};

// C-Suite and admin roles that have full access
const ADMIN_ROLES = ['ceo', 'cto', 'coo', 'director'];

// Minimum org role level to create projects
const MIN_CREATE_PROJECT_LEVEL = ORG_ROLE_LEVELS.project_manager; // 70

// Minimum project role level to manage project (upload, edit)
const MIN_MANAGE_PROJECT_LEVEL = PROJECT_ROLE_LEVELS.contributor; // 50

/**
 * Get the numeric level for an org role
 */
export function getOrgRoleLevel(orgRole: string | null | undefined): number {
  if (!orgRole) return 0;
  return ORG_ROLE_LEVELS[orgRole] ?? 0;
}

/**
 * Get the numeric level for a project role
 */
export function getProjectRoleLevel(projectRole: string | null | undefined): number {
  if (!projectRole) return 0;
  return PROJECT_ROLE_LEVELS[projectRole] ?? 0;
}

/**
 * Check if user is C-Suite/Admin (full access to everything)
 */
export function isAdmin(user: User | null): boolean {
  if (!user) return false;
  return ADMIN_ROLES.includes(user.orgRole);
}

/**
 * Check if user can create new projects
 * Only project_manager (70) and above can create projects
 */
export function canCreateProject(user: User | null): boolean {
  if (!user) return false;
  const level = getOrgRoleLevel(user.orgRole);
  return level >= MIN_CREATE_PROJECT_LEVEL;
}

/**
 * Project member info for permission checking
 */
export interface ProjectMemberInfo {
  userId: string;
  projectRole: string;
  jobRole?: string;
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
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return false;

  // C-Suite/Admin can see all assets
  if (isAdmin(user)) return true;

  // Check if user is a member of the project
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  // Project managers/owners can view assets
  const projectLevel = getProjectRoleLevel(membership.projectRole);
  if (projectLevel >= PROJECT_ROLE_LEVELS.manager) return true;

  // Programmers assigned to the project can view assets
  if (user.jobRole === 'programmer') return true;

  // Everyone else (contributors, viewers, etc.) - NO access
  return false;
}

/**
 * Check if user can upload/manage assets for a project
 * PERMISSIONS:
 * - C-Suite/Admin: Can upload to any project
 * - Project managers/owners (project role): Can upload to their projects
 * - Programmers (job role) assigned to project: Can upload
 * - Contributors/Members with contributor+ project role: Can upload for their assigned tasks
 * - Viewers/Contractors: NO upload access
 */
export function canUploadAsset(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return false;

  // Contractors cannot upload
  if (user.orgRole === 'contractor') return false;

  // C-Suite/Admin can upload to any project
  if (isAdmin(user)) return true;

  // Check if user is a member of the project
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  // Contributors and above can upload (for their assigned tasks)
  const projectLevel = getProjectRoleLevel(membership.projectRole);
  if (projectLevel >= PROJECT_ROLE_LEVELS.contributor) return true;

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
  user: User | null,
  projectMembers: ProjectMemberInfo[],
  assetUploaderId?: string
): boolean {
  if (!user) return false;

  // C-Suite/Admin can delete any asset
  if (isAdmin(user)) return true;

  // Check project membership
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  // Project managers/owners can delete any asset in their project
  const projectLevel = getProjectRoleLevel(membership.projectRole);
  if (projectLevel >= PROJECT_ROLE_LEVELS.manager) return true;

  // Programmers can delete their own uploads
  if (user.jobRole === 'programmer' && assetUploaderId === user.id) return true;

  // Everyone else - NO delete access
  return false;
}

/**
 * Check if user can toggle project status (release/development)
 * - C-Suite/Admin: Can toggle any project
 * - Project managers/owners of the project: Can toggle
 */
export function canToggleProjectStatus(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return false;

  // C-Suite/Admin can toggle any project
  if (isAdmin(user)) return true;

  // Check project role
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  return getProjectRoleLevel(membership.projectRole) >= PROJECT_ROLE_LEVELS.manager;
}

/**
 * Filter projects to only those the user has access to view
 * - C-Suite/Admin: See all projects
 * - Others: Only see projects they are members of
 */
export function filterAccessibleProjects<T extends { id: string; members?: { user: { id: string } }[] }>(
  user: User | null,
  projects: T[]
): T[] {
  if (!user) return [];

  // C-Suite/Admin can see all projects
  if (isAdmin(user)) return projects;

  // Filter to projects where user is a member
  return projects.filter(project =>
    project.members?.some(m => m.user.id === user.id)
  );
}

/**
 * Get user's project role for a specific project
 */
export function getUserProjectRole(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): string | null {
  if (!user) return null;
  const membership = projectMembers.find(m => m.userId === user.id);
  return membership?.projectRole ?? null;
}

/**
 * Check if user can access the Assets page at all
 * Returns true if user is admin, or is a programmer, or is a project manager
 */
export function canAccessAssetsPage(user: User | null): boolean {
  if (!user) return false;

  // Admins can access
  if (isAdmin(user)) return true;

  // Programmers can access (they'll see assets for their projects)
  if (user.jobRole === 'programmer') return true;

  // Project managers (org role) can access
  if (getOrgRoleLevel(user.orgRole) >= ORG_ROLE_LEVELS.project_manager) return true;

  // Everyone else - no access to Assets page
  return false;
}

/**
 * Check if user has asset access for a specific project
 * Used to filter which projects' assets user can see
 */
export function hasAssetAccessForProject(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  return canViewProjectAssets(user, projectMembers);
}

// ============================================
// FINANCE PERMISSIONS
// ============================================

/**
 * Check if user can access the Finances page at all
 * Returns true if user is admin or org-level project manager+
 */
export function canAccessFinancesPage(user: User | null): boolean {
  if (!user) return false;

  // Admins can access all finances
  if (isAdmin(user)) return true;

  // Org-level project managers and above can access
  if (getOrgRoleLevel(user.orgRole) >= ORG_ROLE_LEVELS.project_manager) return true;

  // Everyone else - no access to Finances page
  return false;
}

/**
 * Check if user can view finance data for a specific project
 * - Admins: Can view all projects
 * - Project managers/owners (project role): Can view their project's finances
 */
export function canViewProjectFinances(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return false;

  // Admins can view all finances
  if (isAdmin(user)) return true;

  // Check project membership
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  // Project managers/owners can view finances
  const projectLevel = getProjectRoleLevel(membership.projectRole);
  if (projectLevel >= PROJECT_ROLE_LEVELS.manager) return true;

  // Org-level project managers viewing their assigned projects
  if (getOrgRoleLevel(user.orgRole) >= ORG_ROLE_LEVELS.project_manager) return true;

  // Everyone else - NO access
  return false;
}

/**
 * Check if user can add/edit/delete transactions for a project
 * Same as canViewProjectFinances - managers+ can manage
 */
export function canManageProjectFinances(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  return canViewProjectFinances(user, projectMembers);
}

/**
 * Check if user can set/modify budgets for a project
 * More restrictive - only project owners and admins
 */
export function canManageBudget(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return false;

  // Admins can manage all budgets
  if (isAdmin(user)) return true;

  // Check project membership
  const membership = projectMembers.find(m => m.userId === user.id);
  if (!membership) return false;

  // Only project owners can set budgets
  if (membership.projectRole === 'owner') return true;

  // Everyone else - NO access to budget management
  return false;
}

/**
 * Check if user can view all projects' finances (admin-only feature)
 */
export function canViewAllFinances(user: User | null): boolean {
  if (!user) return false;
  return isAdmin(user);
}

/**
 * Check if user can only add expense transactions (not income)
 * Project managers can add expenses but not income
 * Only admins and project owners can add income
 */
export function canOnlyAddExpenses(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  if (!user) return true;

  // Admins can add both income and expenses
  if (isAdmin(user)) return false;

  // Check project membership
  const membership = projectMembers.find(m => m.userId === user.id);

  // Project owners can add both income and expenses
  if (membership?.projectRole === 'owner') return false;

  // Everyone else (including project managers) can only add expenses
  return true;
}

/**
 * Check if user has finance access for a specific project
 * Used to filter which projects' finances user can see
 */
export function hasFinanceAccessForProject(
  user: User | null,
  projectMembers: ProjectMemberInfo[]
): boolean {
  return canViewProjectFinances(user, projectMembers);
}
