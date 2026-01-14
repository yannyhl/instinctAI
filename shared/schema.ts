import { sql } from "drizzle-orm";
import { relations } from "drizzle-orm";
import {
  pgTable,
  text,
  varchar,
  timestamp,
  boolean,
  integer,
  jsonb,
  index,
  pgEnum,
  unique,
  primaryKey,
  real,
} from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod";

// ============================================
// ENUMS
// ============================================

export const orgRoleEnum = pgEnum("org_role", [
  "ceo",
  "cto",
  "coo",
  "director",
  "project_manager",
  "lead",
  "senior",
  "member",
  "contractor",
]);

export const jobRoleEnum = pgEnum("job_role", [
  "programmer",
  "animator",
  "3d_artist",
  "ui_artist",
  "vfx_artist",
  "sfx_artist",
  "gfx_artist",
  "concept_artist",
  "game_designer",
  "level_designer",
  "qa_tester",
  "project_manager",
  "community_manager",
  "writer",
  "composer",
  "other",
]);

export const projectRoleEnum = pgEnum("project_role", [
  "owner",
  "manager",
  "contributor",
  "viewer",
]);

export const projectStatusEnum = pgEnum("project_status", [
  "in_development",
  "released",
]);

export const developmentPhaseEnum = pgEnum("development_phase", [
  "concept",
  "prototype",
  "alpha",
  "closed_beta",
  "open_beta",
  "early_access",
  "launch_ready",
]);

export const updateStatusEnum = pgEnum("update_status", [
  "planning",
  "in_progress",
  "testing",
  "ready",
  "released",
]);

export const itemStatusEnum = pgEnum("item_status", [
  "pending",
  "in_progress",
  "review",
  "completed",
]);

export const priorityEnum = pgEnum("priority", [
  "low",
  "medium",
  "high",
  "critical",
]);

export const itemTypeEnum = pgEnum("item_type", [
  "fiend",
  "ability",
  "contract",
  "skill",
  "system",
  "ui",
  "environment",
  "other",
]);

export const subtaskTypeEnum = pgEnum("subtask_type", [
  "animation",
  "vfx",
  "sfx",
  "model",
  "art",
  "programming",
  "design",
  "other",
]);

export const attachmentTypeEnum = pgEnum("attachment_type", [
  "image",
  "video",
  "audio",
  "link",
  "file",
  "document",
  "roblox",
  "archive",
]);

// Asset categories for organization
export const assetCategoryEnum = pgEnum("asset_category", [
  "model",      // 3D models, .rbxm, .fbx, etc.
  "map",        // Maps, environments, worlds
  "animation",  // Animation files
  "vfx",        // Visual effects, particles
  "sfx",        // Sound effects
  "music",      // Music, ambience
  "ui",         // UI elements, icons
  "texture",    // Textures, materials
  "script",     // Lua scripts, modules
  "reference",  // Reference images, concepts
  "other",      // Miscellaneous
]);

export const activityTypeEnum = pgEnum("activity_type", [
  "project_created",
  "project_updated",
  "update_created",
  "item_created",
  "item_updated",
  "item_completed",
  "milestone_created",
  "milestone_completed",
  "team_added",
  "team_removed",
  "reference_added",
  "attachment_added",
]);

export const assetTypeEnum = pgEnum("asset_type", [
  "model",
  "texture",
  "animation",
  "sound",
  "music",
  "script",
  "ui_element",
  "vfx",
  "material",
  "font",
  "icon",
  "video",
  "documentation",
  "other",
]);

export const assetStatusEnum = pgEnum("asset_status", [
  "needed",       // Asset is required but not yet started
  "in_progress",  // Asset is being worked on
  "review",       // Asset is ready for review
  "approved",     // Asset has been approved
  "delivered",    // Asset has been delivered/uploaded
]);

export const releaseTypeEnum = pgEnum("release_type", [
  "content_update",
  "patch",
  "hotfix",
  "event",
  "season",
  "beta",
]);

export const releaseStatusEnum = pgEnum("release_status", [
  "planning",
  "in_progress",
  "testing",
  "staging",
  "released",
  "cancelled",
]);

export const documentStatusEnum = pgEnum("document_status", [
  "draft",
  "published",
  "archived",
]);

// ============================================
// FINANCE ENUMS
// ============================================

export const currencyEnum = pgEnum("currency", [
  "robux",
  "usd",
]);

export const transactionCategoryEnum = pgEnum("transaction_category", [
  "programming",
  "animation",
  "modeling",
  "vfx",
  "sfx",
  "marketing",
  "video_trailer",
  "ui",
  "music",
  "other",
]);

export const transactionTypeEnum = pgEnum("transaction_type", [
  "expense",
  "income",
]);

export const paymentMethodEnum = pgEnum("payment_method", [
  "robux_direct",
  "bank_transfer",
  "paypal",
  "other",
]);

// ============================================
// USERS TABLE
// ============================================

export const users = pgTable(
  "users",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Legacy fields (nullable for Roblox-only accounts)
    username: text("username"), // Deprecated: use robloxUsername
    email: text("email"), // Deprecated: not used for Roblox-only auth
    password: text("password"), // Deprecated: not used for Roblox-only auth
    // Display name from Roblox
    name: text("name").notNull(),
    avatar: text("avatar"), // Roblox CDN avatar URL
    jobRole: jobRoleEnum("job_role").default("other").notNull(), // Job function (e.g., Animator, Programmer)
    orgRole: orgRoleEnum("org_role").default("member").notNull(), // Org hierarchy (e.g., Lead, Senior)
    department: text("department"),
    timezone: text("timezone").default("UTC"),
    isActive: boolean("is_active").default(true).notNull(),
    emailVerified: boolean("email_verified").default(false).notNull(),
    notificationPreferences: jsonb("notification_preferences")
      .$type<{
        email: boolean;
        push: boolean;
        milestones: boolean;
        assetUpdates: boolean;
        teamChanges: boolean;
      }>()
      .default({
        email: true,
        push: true,
        milestones: true,
        assetUpdates: false,
        teamChanges: true,
      }),
    lastLoginAt: timestamp("last_login_at"),
    // SECURITY: Account lockout fields to prevent brute force attacks
    failedLoginAttempts: integer("failed_login_attempts").default(0).notNull(),
    lockedUntil: timestamp("locked_until"),
    // Roblox identity fields (primary authentication)
    robloxId: text("roblox_id").unique(), // Primary identifier - must be unique
    robloxUsername: text("roblox_username"), // @username from Roblox
    robloxDisplayName: text("roblox_display_name"),
    robloxVerifiedAt: timestamp("roblox_verified_at"),
    // Discord integration
    discordId: text("discord_id").unique(),
    discordUsername: text("discord_username"),
    discordLinkedAt: timestamp("discord_linked_at"),
    // Roblox group verification (for access control)
    robloxGroupId: text("roblox_group_id"), // Group ID user was verified in
    robloxGroupRank: integer("roblox_group_rank"), // Numeric rank (e.g., 254)
    robloxGroupRoleName: text("roblox_group_role_name"), // Role name (e.g., "Developer")
    groupVerifiedAt: timestamp("group_verified_at"), // When group membership was last verified
    groupVerificationBypassedAt: timestamp("group_verification_bypassed_at"), // For grandfathered users
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("users_email_idx").on(table.email),
    index("users_username_idx").on(table.username),
    index("users_job_role_idx").on(table.jobRole),
    index("users_org_role_idx").on(table.orgRole),
    index("users_roblox_id_idx").on(table.robloxId),
    index("users_discord_id_idx").on(table.discordId),
    index("users_group_verified_idx").on(table.groupVerifiedAt),
  ]
);

// ============================================
// SESSIONS TABLE (for express-session with connect-pg-simple)
// ============================================

export const sessions = pgTable(
  "session",
  {
    sid: varchar("sid").primaryKey(),
    sess: jsonb("sess").notNull(),
    expire: timestamp("expire", { precision: 6 }).notNull(),
  },
  (table) => [index("sessions_expire_idx").on(table.expire)]
);

// ============================================
// PROJECTS TABLE
// ============================================

export const projects = pgTable(
  "projects",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    name: text("name").notNull(),
    description: text("description"),
    status: projectStatusEnum("status").default("in_development").notNull(),
    // Development phase tracking (only for in_development projects)
    currentPhase: developmentPhaseEnum("current_phase").default("concept"),
    phaseStartDate: timestamp("phase_start_date"),
    targetPublicRelease: timestamp("target_public_release"),
    isPubliclyAccessible: boolean("is_publicly_accessible").default(false),
    progress: integer("progress").default(0).notNull(),
    thumbnail: text("thumbnail"),
    videoUrl: text("video_url"),
    dueDate: timestamp("due_date"),
    startDate: timestamp("start_date").defaultNow(),
    createdById: varchar("created_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("projects_status_idx").on(table.status),
    index("projects_due_date_idx").on(table.dueDate),
    index("projects_phase_idx").on(table.currentPhase),
  ]
);

// ============================================
// PROJECT MEMBERS (Junction Table)
// ============================================

export const projectMembers = pgTable(
  "project_members",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    userId: varchar("user_id")
      .references(() => users.id, { onDelete: "cascade" })
      .notNull(),
    projectRole: projectRoleEnum("project_role").default("contributor").notNull(),
    joinedAt: timestamp("joined_at").defaultNow().notNull(),
  },
  (table) => [
    index("project_members_project_idx").on(table.projectId),
    index("project_members_user_idx").on(table.userId),
    unique("project_members_unique").on(table.projectId, table.userId),
  ]
);

// ============================================
// GAME UPDATES (Versioned releases)
// ============================================

export const gameUpdates = pgTable(
  "game_updates",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    version: text("version").notNull(),
    title: text("title").notNull(),
    description: text("description"),
    status: updateStatusEnum("status").default("planning").notNull(),
    dueDate: timestamp("due_date").notNull(),
    notes: text("notes"),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("game_updates_project_idx").on(table.projectId),
    index("game_updates_status_idx").on(table.status),
    index("game_updates_due_date_idx").on(table.dueDate),
  ]
);

// ============================================
// UPDATE SECTIONS (Groups within updates)
// ============================================

export const updateSections = pgTable(
  "update_sections",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    updateId: varchar("update_id")
      .references(() => gameUpdates.id, { onDelete: "cascade" })
      .notNull(),
    title: text("title").notNull(),
    description: text("description"),
    icon: text("icon"),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [index("update_sections_update_idx").on(table.updateId)]
);

// ============================================
// CONTENT ITEMS (Tasks/features)
// ============================================

export const contentItems = pgTable(
  "content_items",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    sectionId: varchar("section_id")
      .references(() => updateSections.id, { onDelete: "cascade" })
      .notNull(),
    name: text("name").notNull(),
    type: itemTypeEnum("type"),
    status: itemStatusEnum("status").default("pending").notNull(),
    priority: priorityEnum("priority").default("medium"),
    notes: text("notes"),
    dueDate: timestamp("due_date"),
    assigneeId: varchar("assignee_id").references(() => users.id, {
      onDelete: "set null",
    }),
    dependencies: text("dependencies").array(),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("content_items_section_idx").on(table.sectionId),
    index("content_items_status_idx").on(table.status),
    index("content_items_assignee_idx").on(table.assigneeId),
    index("content_items_priority_idx").on(table.priority),
  ]
);

// ============================================
// SUBTASKS (Granular tasks within items)
// ============================================

export const subtasks = pgTable(
  "subtasks",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    itemId: varchar("item_id")
      .references(() => contentItems.id, { onDelete: "cascade" })
      .notNull(),
    name: text("name").notNull(),
    type: subtaskTypeEnum("type").default("other").notNull(),
    status: itemStatusEnum("status").default("pending").notNull(),
    notes: text("notes"),
    dueDate: timestamp("due_date"),
    assigneeId: varchar("assignee_id").references(() => users.id, {
      onDelete: "set null",
    }),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("subtasks_item_idx").on(table.itemId),
    index("subtasks_status_idx").on(table.status),
    index("subtasks_assignee_idx").on(table.assigneeId),
  ]
);

// ============================================
// ATTACHMENTS (For items and subtasks)
// ============================================

export const attachments = pgTable(
  "attachments",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    itemId: varchar("item_id").references(() => contentItems.id, {
      onDelete: "cascade",
    }),
    subtaskId: varchar("subtask_id").references(() => subtasks.id, {
      onDelete: "cascade",
    }),
    // For standalone project assets (not attached to item/subtask)
    projectId: varchar("project_id").references(() => projects.id, {
      onDelete: "cascade",
    }),
    name: text("name").notNull(),
    type: attachmentTypeEnum("type").notNull(),
    url: text("url").notNull(),
    thumbnail: text("thumbnail"),
    fileSize: integer("file_size"),
    mimeType: text("mime_type"),
    description: text("description"),
    // Asset category for organization
    category: assetCategoryEnum("category"),
    // Week-based organization for assets
    weekNumber: integer("week_number"),
    year: integer("year"),
    uploadedById: varchar("uploaded_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("attachments_item_idx").on(table.itemId),
    index("attachments_subtask_idx").on(table.subtaskId),
    index("attachments_type_idx").on(table.type),
    index("attachments_project_idx").on(table.projectId),
    index("attachments_project_week_idx").on(table.projectId, table.year, table.weekNumber),
  ]
);

// ============================================
// ASSET REQUIREMENTS (What assets are needed for items)
// ============================================

export const assetRequirements = pgTable(
  "asset_requirements",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    itemId: varchar("item_id")
      .references(() => contentItems.id, { onDelete: "cascade" })
      .notNull(),
    name: text("name").notNull(), // e.g., "Dragon Model", "Fire Breath VFX"
    type: assetTypeEnum("type").notNull(),
    status: assetStatusEnum("status").default("needed").notNull(),
    description: text("description"), // Details about what's needed
    specifications: text("specifications"), // Technical specs or requirements
    priority: priorityEnum("priority").default("medium"),
    assigneeId: varchar("assignee_id").references(() => users.id, {
      onDelete: "set null",
    }),
    // Link to the actual attachment once delivered
    deliveredAttachmentId: varchar("delivered_attachment_id").references(
      () => attachments.id,
      { onDelete: "set null" }
    ),
    dueDate: timestamp("due_date"),
    deliveredAt: timestamp("delivered_at"),
    approvedById: varchar("approved_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    approvedAt: timestamp("approved_at"),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("asset_requirements_item_idx").on(table.itemId),
    index("asset_requirements_status_idx").on(table.status),
    index("asset_requirements_type_idx").on(table.type),
    index("asset_requirements_assignee_idx").on(table.assigneeId),
  ]
);

// ============================================
// PROJECT REFERENCES (GDD, style guides, etc.)
// ============================================

export const projectReferences = pgTable(
  "project_references",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    title: text("title").notNull(),
    type: attachmentTypeEnum("type").notNull(),
    url: text("url"),
    description: text("description"),
    addedById: varchar("added_by_id")
      .references(() => users.id, { onDelete: "set null" })
      .notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [index("project_references_project_idx").on(table.projectId)]
);

// ============================================
// MILESTONES
// ============================================

export const milestones = pgTable(
  "milestones",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    title: text("title").notNull(),
    description: text("description"),
    dueDate: timestamp("due_date").notNull(),
    completed: boolean("completed").default(false).notNull(),
    completedAt: timestamp("completed_at"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("milestones_project_idx").on(table.projectId),
    index("milestones_due_date_idx").on(table.dueDate),
    index("milestones_completed_idx").on(table.completed),
  ]
);

// ============================================
// RELEASE CYCLES (For Timeline)
// ============================================

export const releaseCycles = pgTable(
  "release_cycles",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    version: text("version").notNull(),
    title: text("title").notNull(),
    description: text("description"),
    type: releaseTypeEnum("type").default("content_update").notNull(),
    status: releaseStatusEnum("status").default("planning").notNull(),
    priority: priorityEnum("priority").default("medium").notNull(),
    plannedStartDate: timestamp("planned_start_date"),
    plannedEndDate: timestamp("planned_end_date").notNull(),
    actualStartDate: timestamp("actual_start_date"),
    actualEndDate: timestamp("actual_end_date"),
    color: text("color"),
    notes: text("notes"),
    changelog: jsonb("changelog").$type<string[]>(),
    tags: jsonb("tags").$type<string[]>(),
    createdById: varchar("created_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("release_cycles_project_idx").on(table.projectId),
    index("release_cycles_status_idx").on(table.status),
    index("release_cycles_end_date_idx").on(table.plannedEndDate),
  ]
);

// ============================================
// RELEASE REQUIREMENTS
// ============================================

export const releaseRequirements = pgTable(
  "release_requirements",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    releaseCycleId: varchar("release_cycle_id")
      .references(() => releaseCycles.id, { onDelete: "cascade" })
      .notNull(),
    title: text("title").notNull(),
    description: text("description"),
    category: text("category"),
    status: itemStatusEnum("status").default("pending").notNull(),
    priority: priorityEnum("priority").default("medium"),
    assigneeId: varchar("assignee_id").references(() => users.id, {
      onDelete: "set null",
    }),
    estimatedHours: integer("estimated_hours"),
    actualHours: integer("actual_hours"),
    dueDate: timestamp("due_date"),
    completedAt: timestamp("completed_at"),
    sortOrder: integer("sort_order").default(0).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("release_requirements_release_idx").on(table.releaseCycleId),
    index("release_requirements_assignee_idx").on(table.assigneeId),
  ]
);

// ============================================
// RELEASE TEAM ASSIGNMENTS
// ============================================

export const releaseTeamAssignments = pgTable(
  "release_team_assignments",
  {
    releaseCycleId: varchar("release_cycle_id")
      .references(() => releaseCycles.id, { onDelete: "cascade" })
      .notNull(),
    userId: varchar("user_id")
      .references(() => users.id, { onDelete: "cascade" })
      .notNull(),
    role: text("role").default("contributor"),
    assignedAt: timestamp("assigned_at").defaultNow().notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.releaseCycleId, table.userId] }),
  ]
);

// ============================================
// TEAM INVITES
// ============================================

export const teamInvites = pgTable(
  "team_invites",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    email: text("email").notNull(),
    orgRole: orgRoleEnum("org_role").default("member").notNull(),
    token: text("token").notNull().unique(),
    invitedById: varchar("invited_by_id")
      .references(() => users.id, { onDelete: "cascade" })
      .notNull(),
    expiresAt: timestamp("expires_at").notNull(),
    acceptedAt: timestamp("accepted_at"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("team_invites_email_idx").on(table.email),
    index("team_invites_token_idx").on(table.token),
    index("team_invites_expires_idx").on(table.expiresAt),
  ]
);

// ============================================
// ACTIVITY LOGS
// ============================================

export const activityLogs = pgTable(
  "activity_logs",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    userId: varchar("user_id")
      .references(() => users.id, { onDelete: "set null" })
      .notNull(),
    type: activityTypeEnum("type").notNull(),
    message: text("message").notNull(),
    metadata: jsonb("metadata").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("activity_logs_project_idx").on(table.projectId),
    index("activity_logs_user_idx").on(table.userId),
    index("activity_logs_type_idx").on(table.type),
    index("activity_logs_created_at_idx").on(table.createdAt),
  ]
);

// ============================================
// SECURITY AUDIT LOGS
// ============================================

export const securityAuditActionEnum = pgEnum("security_audit_action", [
  "LOGIN_SUCCESS",
  "LOGIN_FAILED",
  "LOGIN_LOCKED",
  "LOGOUT",
  "PASSWORD_CHANGED",
  "ROLE_CHANGED",
  "USER_CREATED",
  "USER_DEACTIVATED",
  "USER_REACTIVATED",
  "SESSION_CREATED",
  "SESSION_DESTROYED",
  "PERMISSION_DENIED",
  "ADMIN_ACTION",
]);

export const securityAuditLogs = pgTable(
  "security_audit_logs",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    action: securityAuditActionEnum("action").notNull(),
    // Who performed the action
    performedById: varchar("performed_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    // Who was affected (for role changes, deactivations, etc.)
    targetUserId: varchar("target_user_id").references(() => users.id, {
      onDelete: "set null",
    }),
    // Resource affected (optional)
    targetResourceType: text("target_resource_type"),
    targetResourceId: varchar("target_resource_id"),
    // Change details
    previousValue: jsonb("previous_value"),
    newValue: jsonb("new_value"),
    // Request metadata
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    // Additional context
    metadata: jsonb("metadata").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("security_audit_logs_action_idx").on(table.action),
    index("security_audit_logs_performed_by_idx").on(table.performedById),
    index("security_audit_logs_target_user_idx").on(table.targetUserId),
    index("security_audit_logs_created_at_idx").on(table.createdAt),
  ]
);

// Relations
export const securityAuditLogsRelations = relations(securityAuditLogs, ({ one }) => ({
  performedBy: one(users, {
    fields: [securityAuditLogs.performedById],
    references: [users.id],
    relationName: "auditPerformer",
  }),
  targetUser: one(users, {
    fields: [securityAuditLogs.targetUserId],
    references: [users.id],
    relationName: "auditTarget",
  }),
}));

// Types
export type SecurityAuditLog = typeof securityAuditLogs.$inferSelect;
export type NewSecurityAuditLog = typeof securityAuditLogs.$inferInsert;
export type SecurityAuditAction = (typeof securityAuditActionEnum.enumValues)[number];

// ============================================
// DISCORD NOTIFICATIONS (deadline reminders)
// ============================================

export const discordNotifications = pgTable(
  "discord_notifications",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    userId: varchar("user_id")
      .references(() => users.id, { onDelete: "cascade" })
      .notNull(),
    // Type of target: 'content_item' or 'project'
    targetType: text("target_type").notNull(),
    // ID of the content item or project
    targetId: varchar("target_id").notNull(),
    // Notification type: 'deadline_reminder'
    notificationType: text("notification_type").notNull(),
    sentAt: timestamp("sent_at").defaultNow().notNull(),
    // Discord message ID for reference
    discordMessageId: text("discord_message_id"),
  },
  (table) => [
    index("discord_notifications_user_idx").on(table.userId),
    index("discord_notifications_target_idx").on(table.targetType, table.targetId),
    // Unique constraint to prevent duplicate notifications
    unique("discord_notifications_unique").on(
      table.userId,
      table.targetType,
      table.targetId,
      table.notificationType
    ),
  ]
);

// ============================================
// DOCUMENTS (Notion-style docs)
// ============================================

// TipTap document types
export interface TipTapMark {
  type: string;
  attrs?: Record<string, unknown>;
}

export interface TipTapNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: TipTapNode[];
  marks?: TipTapMark[];
  text?: string;
}

export interface TipTapDocument {
  type: "doc";
  content: TipTapNode[];
}

export const documents = pgTable(
  "documents",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    parentId: varchar("parent_id"),
    title: text("title").notNull(),
    // TipTap JSON document content
    content: jsonb("content").$type<TipTapDocument>(),
    // Plain text for search (extracted from content)
    contentText: text("content_text"),
    icon: text("icon"), // Emoji or icon name
    status: documentStatusEnum("status").default("draft").notNull(),
    sortOrder: integer("sort_order").default(0).notNull(),
    // Metadata
    createdById: varchar("created_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    lastEditedById: varchar("last_edited_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("documents_project_idx").on(table.projectId),
    index("documents_parent_idx").on(table.parentId),
    index("documents_status_idx").on(table.status),
    index("documents_sort_idx").on(table.projectId, table.sortOrder),
  ]
);

// ============================================
// DOCUMENT LINKS (Junction table for backlinks)
// ============================================

export const documentLinks = pgTable(
  "document_links",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    sourceDocumentId: varchar("source_document_id")
      .references(() => documents.id, { onDelete: "cascade" })
      .notNull(),
    targetDocumentId: varchar("target_document_id")
      .references(() => documents.id, { onDelete: "cascade" })
      .notNull(),
    // Context: text around the link for preview
    linkContext: text("link_context"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("document_links_source_idx").on(table.sourceDocumentId),
    index("document_links_target_idx").on(table.targetDocumentId),
    unique("document_links_unique").on(
      table.sourceDocumentId,
      table.targetDocumentId
    ),
  ]
);

// ============================================
// FINANCE TRANSACTIONS
// ============================================

export const financeTransactions = pgTable(
  "finance_transactions",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Project association (required for access control)
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    // Transaction details
    type: transactionTypeEnum("type").default("expense").notNull(),
    category: transactionCategoryEnum("category").notNull(),
    currency: currencyEnum("currency").notNull(),
    // Amount stored as integer (cents for USD, raw for Robux)
    amount: integer("amount").notNull(),
    // Description and notes
    description: text("description").notNull(),
    notes: text("notes"),
    // Payee information
    payeeName: text("payee_name"),
    payeeRobloxUsername: text("payee_roblox_username"),
    // Payment tracking
    paymentMethod: paymentMethodEnum("payment_method").notNull(),
    paymentReference: text("payment_reference"),
    // Week-based organization
    weekNumber: integer("week_number").notNull(),
    year: integer("year").notNull(),
    transactionDate: timestamp("transaction_date").notNull(),
    // Receipt/Invoice attachment
    receiptUrl: text("receipt_url"),
    receiptThumbnail: text("receipt_thumbnail"),
    // Audit fields
    createdById: varchar("created_by_id")
      .references(() => users.id, { onDelete: "set null" }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => [
    index("finance_transactions_project_idx").on(table.projectId),
    index("finance_transactions_category_idx").on(table.category),
    index("finance_transactions_currency_idx").on(table.currency),
    index("finance_transactions_project_week_idx").on(
      table.projectId,
      table.year,
      table.weekNumber
    ),
    index("finance_transactions_date_idx").on(table.transactionDate),
    index("finance_transactions_type_idx").on(table.type),
    index("finance_transactions_created_by_idx").on(table.createdById),
  ]
);

// ============================================
// PROJECT BUDGETS
// ============================================

export const projectBudgets = pgTable(
  "project_budgets",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Project association
    projectId: varchar("project_id")
      .references(() => projects.id, { onDelete: "cascade" })
      .notNull(),
    // Budget period (optional - if null, applies to entire project)
    weekNumber: integer("week_number"),
    year: integer("year"),
    // Category-specific budget
    category: transactionCategoryEnum("category").notNull(),
    currency: currencyEnum("currency").notNull(),
    // Budget amount (stored as integer: cents for USD, raw for Robux)
    budgetAmount: integer("budget_amount").notNull(),
    // Alert threshold (percentage 0-100)
    alertThreshold: integer("alert_threshold").default(80),
    // Notes
    notes: text("notes"),
    // Audit fields
    createdById: varchar("created_by_id")
      .references(() => users.id, { onDelete: "set null" }),
    updatedById: varchar("updated_by_id")
      .references(() => users.id, { onDelete: "set null" }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("project_budgets_project_idx").on(table.projectId),
    index("project_budgets_project_category_idx").on(
      table.projectId,
      table.category,
      table.currency
    ),
    // Unique constraint for overall project budgets (when week/year are null)
    unique("project_budgets_unique").on(
      table.projectId,
      table.category,
      table.currency
    ),
  ]
);

// ============================================
// RELATIONS
// ============================================

export const usersRelations = relations(users, ({ many }) => ({
  projectMemberships: many(projectMembers),
  assignedItems: many(contentItems),
  assignedSubtasks: many(subtasks),
  activityLogs: many(activityLogs),
  uploadedAttachments: many(attachments),
  addedReferences: many(projectReferences),
  releaseAssignments: many(releaseTeamAssignments),
  assignedRequirements: many(releaseRequirements),
  createdTransactions: many(financeTransactions),
  createdBudgets: many(projectBudgets),
}));

export const projectsRelations = relations(projects, ({ one, many }) => ({
  createdBy: one(users, {
    fields: [projects.createdById],
    references: [users.id],
  }),
  members: many(projectMembers),
  updates: many(gameUpdates),
  references: many(projectReferences),
  milestones: many(milestones),
  activityLogs: many(activityLogs),
  releaseCycles: many(releaseCycles),
  assets: many(attachments),
  documents: many(documents),
  financeTransactions: many(financeTransactions),
  budgets: many(projectBudgets),
}));

export const projectMembersRelations = relations(projectMembers, ({ one }) => ({
  project: one(projects, {
    fields: [projectMembers.projectId],
    references: [projects.id],
  }),
  user: one(users, {
    fields: [projectMembers.userId],
    references: [users.id],
  }),
}));

export const gameUpdatesRelations = relations(gameUpdates, ({ one, many }) => ({
  project: one(projects, {
    fields: [gameUpdates.projectId],
    references: [projects.id],
  }),
  sections: many(updateSections),
}));

export const updateSectionsRelations = relations(
  updateSections,
  ({ one, many }) => ({
    update: one(gameUpdates, {
      fields: [updateSections.updateId],
      references: [gameUpdates.id],
    }),
    items: many(contentItems),
  })
);

export const contentItemsRelations = relations(
  contentItems,
  ({ one, many }) => ({
    section: one(updateSections, {
      fields: [contentItems.sectionId],
      references: [updateSections.id],
    }),
    assignee: one(users, {
      fields: [contentItems.assigneeId],
      references: [users.id],
    }),
    subtasks: many(subtasks),
    attachments: many(attachments),
    assetRequirements: many(assetRequirements),
  })
);

export const assetRequirementsRelations = relations(
  assetRequirements,
  ({ one }) => ({
    item: one(contentItems, {
      fields: [assetRequirements.itemId],
      references: [contentItems.id],
    }),
    assignee: one(users, {
      fields: [assetRequirements.assigneeId],
      references: [users.id],
    }),
    approvedBy: one(users, {
      fields: [assetRequirements.approvedById],
      references: [users.id],
    }),
    deliveredAttachment: one(attachments, {
      fields: [assetRequirements.deliveredAttachmentId],
      references: [attachments.id],
    }),
  })
);

export const subtasksRelations = relations(subtasks, ({ one, many }) => ({
  item: one(contentItems, {
    fields: [subtasks.itemId],
    references: [contentItems.id],
  }),
  assignee: one(users, {
    fields: [subtasks.assigneeId],
    references: [users.id],
  }),
  attachments: many(attachments),
}));

export const attachmentsRelations = relations(attachments, ({ one }) => ({
  item: one(contentItems, {
    fields: [attachments.itemId],
    references: [contentItems.id],
  }),
  subtask: one(subtasks, {
    fields: [attachments.subtaskId],
    references: [subtasks.id],
  }),
  project: one(projects, {
    fields: [attachments.projectId],
    references: [projects.id],
  }),
  uploadedBy: one(users, {
    fields: [attachments.uploadedById],
    references: [users.id],
  }),
}));

export const projectReferencesRelations = relations(
  projectReferences,
  ({ one }) => ({
    project: one(projects, {
      fields: [projectReferences.projectId],
      references: [projects.id],
    }),
    addedBy: one(users, {
      fields: [projectReferences.addedById],
      references: [users.id],
    }),
  })
);

export const milestonesRelations = relations(milestones, ({ one }) => ({
  project: one(projects, {
    fields: [milestones.projectId],
    references: [projects.id],
  }),
}));

export const releaseCyclesRelations = relations(
  releaseCycles,
  ({ one, many }) => ({
    project: one(projects, {
      fields: [releaseCycles.projectId],
      references: [projects.id],
    }),
    createdBy: one(users, {
      fields: [releaseCycles.createdById],
      references: [users.id],
    }),
    requirements: many(releaseRequirements),
    teamAssignments: many(releaseTeamAssignments),
  })
);

export const releaseRequirementsRelations = relations(
  releaseRequirements,
  ({ one }) => ({
    releaseCycle: one(releaseCycles, {
      fields: [releaseRequirements.releaseCycleId],
      references: [releaseCycles.id],
    }),
    assignee: one(users, {
      fields: [releaseRequirements.assigneeId],
      references: [users.id],
    }),
  })
);

export const releaseTeamAssignmentsRelations = relations(
  releaseTeamAssignments,
  ({ one }) => ({
    releaseCycle: one(releaseCycles, {
      fields: [releaseTeamAssignments.releaseCycleId],
      references: [releaseCycles.id],
    }),
    user: one(users, {
      fields: [releaseTeamAssignments.userId],
      references: [users.id],
    }),
  })
);

export const activityLogsRelations = relations(activityLogs, ({ one }) => ({
  project: one(projects, {
    fields: [activityLogs.projectId],
    references: [projects.id],
  }),
  user: one(users, {
    fields: [activityLogs.userId],
    references: [users.id],
  }),
}));

export const documentsRelations = relations(documents, ({ one, many }) => ({
  project: one(projects, {
    fields: [documents.projectId],
    references: [projects.id],
  }),
  parent: one(documents, {
    fields: [documents.parentId],
    references: [documents.id],
    relationName: "parentChild",
  }),
  children: many(documents, { relationName: "parentChild" }),
  createdBy: one(users, {
    fields: [documents.createdById],
    references: [users.id],
    relationName: "documentCreator",
  }),
  lastEditedBy: one(users, {
    fields: [documents.lastEditedById],
    references: [users.id],
    relationName: "documentEditor",
  }),
  outgoingLinks: many(documentLinks, { relationName: "sourceLinks" }),
  incomingLinks: many(documentLinks, { relationName: "targetLinks" }),
}));

export const documentLinksRelations = relations(documentLinks, ({ one }) => ({
  sourceDocument: one(documents, {
    fields: [documentLinks.sourceDocumentId],
    references: [documents.id],
    relationName: "sourceLinks",
  }),
  targetDocument: one(documents, {
    fields: [documentLinks.targetDocumentId],
    references: [documents.id],
    relationName: "targetLinks",
  }),
}));

export const financeTransactionsRelations = relations(
  financeTransactions,
  ({ one }) => ({
    project: one(projects, {
      fields: [financeTransactions.projectId],
      references: [projects.id],
    }),
    createdBy: one(users, {
      fields: [financeTransactions.createdById],
      references: [users.id],
    }),
  })
);

export const projectBudgetsRelations = relations(
  projectBudgets,
  ({ one }) => ({
    project: one(projects, {
      fields: [projectBudgets.projectId],
      references: [projects.id],
    }),
    createdBy: one(users, {
      fields: [projectBudgets.createdById],
      references: [users.id],
      relationName: "budgetCreator",
    }),
    updatedBy: one(users, {
      fields: [projectBudgets.updatedById],
      references: [users.id],
      relationName: "budgetUpdater",
    }),
  })
);

// ============================================
// ZOD VALIDATION SCHEMAS
// ============================================

// Auth schemas (DEPRECATED - Roblox OAuth only)
// These are kept for backwards compatibility but should not be used
export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z
  .object({
    email: z.string().email("Invalid email address"),
    username: z.string().min(3, "Username must be at least 3 characters").max(50),
    name: z.string().min(2, "Name must be at least 2 characters").max(100),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
      .regex(/[a-z]/, "Password must contain at least one lowercase letter")
      .regex(/[0-9]/, "Password must contain at least one number"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

// User schemas - updated for Roblox-only authentication
export const insertUserSchema = createInsertSchema(users, {
  email: z.string().email().optional().nullable(),
  password: z.string().optional().nullable(),
  name: z.string().min(1).max(100),
  username: z.string().min(3).max(50).optional().nullable(),
  robloxId: z.string().optional().nullable(),
  robloxUsername: z.string().optional().nullable(),
  robloxDisplayName: z.string().optional().nullable(),
  avatar: z.string().url().optional().nullable(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  lastLoginAt: true,
});

// Schema for creating user from Roblox OAuth
export const createRobloxUserSchema = z.object({
  robloxId: z.string().min(1, "Roblox ID is required"),
  robloxUsername: z.string().nullable().optional(),
  robloxDisplayName: z.string().nullable().optional(),
  name: z.string().min(1, "Name is required"),
  avatar: z.string().url().nullable().optional(),
  orgRole: z.enum(["ceo", "cto", "director", "project_manager", "lead", "senior", "member", "contractor"]).default("member"),
  jobRole: z.enum(["programmer", "animator", "3d_artist", "ui_artist", "vfx_artist", "sfx_artist", "gfx_artist", "concept_artist", "game_designer", "level_designer", "qa_tester", "project_manager", "community_manager", "writer", "composer", "other"]).default("other"),
  // Roblox group verification fields
  robloxGroupId: z.string().nullable().optional(),
  robloxGroupRank: z.number().int().nullable().optional(),
  robloxGroupRoleName: z.string().nullable().optional(),
  groupVerifiedAt: z.date().nullable().optional(),
  groupVerificationBypassedAt: z.date().nullable().optional(),
});

export const updateUserSchema = createInsertSchema(users)
  .partial()
  .omit({
    id: true,
    password: true,
    createdAt: true,
    updatedAt: true,
    deletedAt: true,
  });

export const safeUserSchema = createSelectSchema(users).omit({ password: true });

// Project schemas
export const insertProjectSchema = createInsertSchema(projects, {
  name: z.string().min(1, "Project name is required").max(100),
  description: z.string().max(1000).optional(),
  thumbnail: z.string().url().optional().or(z.literal("")),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  progress: true,
  createdById: true,
});

export const updateProjectSchema = insertProjectSchema.partial();

export const projectFilterSchema = z.object({
  status: z.enum(["in_development", "released", "all"]).optional().default("all"),
  phase: z.enum(["concept", "prototype", "alpha", "closed_beta", "open_beta", "early_access", "launch_ready", "all"]).optional(),
  search: z.string().optional(),
  sortBy: z.enum(["name", "updated", "progress", "dueDate"]).optional().default("updated"),
  page: z.coerce.number().min(1).optional().default(1),
  limit: z.coerce.number().min(1).max(100).optional().default(20),
});

// Development phase type
export type DevelopmentPhase = "concept" | "prototype" | "alpha" | "closed_beta" | "open_beta" | "early_access" | "launch_ready";

// Project Member schemas
export const insertProjectMemberSchema = createInsertSchema(projectMembers, {
  projectRole: z.enum(["owner", "manager", "contributor", "viewer"]),
}).omit({ id: true, joinedAt: true });

export const updateProjectMemberSchema = z.object({
  projectRole: z.enum(["owner", "manager", "contributor", "viewer"]),
});

// Game Update schemas
export const insertGameUpdateSchema = createInsertSchema(gameUpdates, {
  version: z.string().min(1).max(20),
  title: z.string().min(1).max(200),
  dueDate: z.coerce.date(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  sortOrder: true,
});

export const updateGameUpdateSchema = insertGameUpdateSchema.partial();

// Section schemas
export const insertSectionSchema = createInsertSchema(updateSections, {
  title: z.string().min(1).max(100),
  icon: z.string().max(50).optional(),
}).omit({ id: true, createdAt: true, updatedAt: true, sortOrder: true });

export const updateSectionSchema = insertSectionSchema.partial();

// Content Item schemas
export const insertContentItemSchema = createInsertSchema(contentItems, {
  name: z.string().min(1).max(200),
  notes: z.string().max(5000).optional(),
  dueDate: z.coerce.date().optional(),
  dependencies: z.array(z.string().uuid()).optional(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  sortOrder: true,
});

export const updateContentItemSchema = insertContentItemSchema.partial();

export const bulkUpdateItemsStatusSchema = z.object({
  itemIds: z.array(z.string().uuid()).min(1),
  status: z.enum(["pending", "in_progress", "review", "completed"]),
});

// Subtask schemas
export const insertSubtaskSchema = createInsertSchema(subtasks, {
  name: z.string().min(1).max(200),
  dueDate: z.coerce.date().optional().nullable(),
}).omit({ id: true, createdAt: true, updatedAt: true, sortOrder: true });

export const updateSubtaskSchema = insertSubtaskSchema.partial();

// Attachment schemas
export const insertAttachmentSchema = createInsertSchema(attachments, {
  name: z.string().min(1).max(255),
  url: z.string().url(),
}).omit({ id: true, createdAt: true, uploadedById: true });

export const uploadFileSchema = z.object({
  name: z.string().min(1).max(255),
  mimeType: z.string(),
  size: z.number().max(50 * 1024 * 1024), // 50MB max
});

// Reference schemas
export const insertReferenceSchema = createInsertSchema(projectReferences, {
  title: z.string().min(1).max(200),
  url: z.string().max(2000).optional(), // Allow any string for URL (users often omit protocol)
  description: z.string().max(1000).optional(),
}).omit({ id: true, createdAt: true, updatedAt: true });

export const updateReferenceSchema = insertReferenceSchema.partial();

// Asset Requirement schemas
export const insertAssetRequirementSchema = createInsertSchema(assetRequirements, {
  name: z.string().min(1, "Asset name is required").max(200),
  description: z.string().max(1000).optional(),
  specifications: z.string().max(2000).optional(),
  dueDate: z.coerce.date().optional(),
}).omit({ id: true, createdAt: true, updatedAt: true, sortOrder: true, deliveredAt: true, approvedAt: true });

export const updateAssetRequirementSchema = insertAssetRequirementSchema.partial();

// Milestone schemas
export const insertMilestoneSchema = createInsertSchema(milestones, {
  title: z.string().min(1).max(200),
  description: z.string().max(1000).optional(),
  dueDate: z.coerce.date(),
}).omit({ id: true, createdAt: true, updatedAt: true, completedAt: true });

export const updateMilestoneSchema = insertMilestoneSchema.partial();

// Release Cycle schemas
export const insertReleaseCycleSchema = createInsertSchema(releaseCycles, {
  version: z.string().min(1).max(20),
  title: z.string().min(1).max(200),
  plannedEndDate: z.coerce.date(),
  changelog: z.array(z.string()).nullable().optional(),
  tags: z.array(z.string()).nullable().optional(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  createdById: true,
});

export const updateReleaseCycleSchema = insertReleaseCycleSchema.partial();

// Release Requirement schemas
export const insertReleaseRequirementSchema = createInsertSchema(releaseRequirements, {
  title: z.string().min(1).max(500),
}).omit({ id: true, createdAt: true, updatedAt: true, sortOrder: true });

export const updateReleaseRequirementSchema = insertReleaseRequirementSchema.partial();

// Document schemas
export const insertDocumentSchema = createInsertSchema(documents, {
  title: z.string().min(1, "Title is required").max(200),
  icon: z.string().max(50).optional().nullable(),
  content: z.any().optional(), // TipTap JSON content
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  sortOrder: true,
  contentText: true,
  createdById: true,
  lastEditedById: true,
});

export const updateDocumentSchema = insertDocumentSchema.partial();

export const documentFilterSchema = z.object({
  status: z.enum(["draft", "published", "archived", "all"]).optional().default("all"),
  search: z.string().optional(),
  parentId: z.string().optional().nullable(),
});

// Document Link schemas
export const insertDocumentLinkSchema = createInsertSchema(documentLinks, {
  linkContext: z.string().max(500).optional(),
}).omit({ id: true, createdAt: true });

// ============================================
// FINANCE SCHEMAS
// ============================================

// Transaction categories array for validation
export const TRANSACTION_CATEGORIES = [
  "programming",
  "animation",
  "modeling",
  "vfx",
  "sfx",
  "marketing",
  "video_trailer",
  "ui",
  "music",
  "other",
] as const;

// Finance Transaction schemas
export const insertFinanceTransactionSchema = createInsertSchema(financeTransactions, {
  description: z.string().max(500).optional().nullable(),
  notes: z.string().max(2000).optional().nullable(),
  amount: z.number().int().positive("Amount must be positive"),
  weekNumber: z.number().int().min(1).max(53),
  year: z.number().int().min(2020).max(2100),
  transactionDate: z.coerce.date(),
  payeeName: z.string().max(200).optional().nullable(),
  payeeRobloxUsername: z.string().max(50).optional().nullable(),
  paymentReference: z.string().max(200).optional().nullable(),
  receiptUrl: z.string().url().optional().nullable(),
  receiptThumbnail: z.string().url().optional().nullable(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  createdById: true,
});

export const updateFinanceTransactionSchema = insertFinanceTransactionSchema.partial();

// Project Budget schemas
export const insertProjectBudgetSchema = createInsertSchema(projectBudgets, {
  budgetAmount: z.number().int().positive("Budget must be positive"),
  alertThreshold: z.number().int().min(0).max(100).optional().default(80),
  weekNumber: z.number().int().min(1).max(53).optional().nullable(),
  year: z.number().int().min(2020).max(2100).optional().nullable(),
  notes: z.string().max(1000).optional().nullable(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  createdById: true,
  updatedById: true,
});

export const updateProjectBudgetSchema = insertProjectBudgetSchema.partial();

// Finance query/filter schemas
export const financeQuerySchema = z.object({
  projectId: z.string().uuid().optional(),
  category: z.enum(TRANSACTION_CATEGORIES).optional(),
  currency: z.enum(["robux", "usd"]).optional(),
  type: z.enum(["expense", "income"]).optional(),
  year: z.coerce.number().int().optional(),
  weekNumber: z.coerce.number().int().min(1).max(53).optional(),
  startDate: z.coerce.date().optional(),
  endDate: z.coerce.date().optional(),
  search: z.string().optional(),
  page: z.coerce.number().min(1).optional().default(1),
  limit: z.coerce.number().min(1).max(100).optional().default(50),
});

export const budgetQuerySchema = z.object({
  projectId: z.string().uuid(),
  year: z.coerce.number().int().optional(),
  weekNumber: z.coerce.number().int().min(1).max(53).optional(),
  category: z.enum(TRANSACTION_CATEGORIES).optional(),
  currency: z.enum(["robux", "usd"]).optional(),
});

// ============================================
// TYPE EXPORTS
// ============================================

export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;
export type SafeUser = z.infer<typeof safeUserSchema>;

// User with project memberships (returned by /api/users)
export interface UserProjectMembership {
  projectId: string;
  projectName: string;
  projectRole: ProjectRole;
}

export interface SafeUserWithProjects extends SafeUser {
  projectMemberships: UserProjectMembership[];
}

export type InsertUser = z.infer<typeof insertUserSchema>;
export type InsertRobloxUser = z.infer<typeof createRobloxUserSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;

export type Project = typeof projects.$inferSelect;
export type NewProject = typeof projects.$inferInsert;
export type InsertProject = z.infer<typeof insertProjectSchema>;

export type ProjectMember = typeof projectMembers.$inferSelect;
export type NewProjectMember = typeof projectMembers.$inferInsert;

export type GameUpdate = typeof gameUpdates.$inferSelect;
export type NewGameUpdate = typeof gameUpdates.$inferInsert;

export type UpdateSection = typeof updateSections.$inferSelect;
export type NewUpdateSection = typeof updateSections.$inferInsert;

export type ContentItem = typeof contentItems.$inferSelect;
export type NewContentItem = typeof contentItems.$inferInsert;

export type Subtask = typeof subtasks.$inferSelect;
export type NewSubtask = typeof subtasks.$inferInsert;

export type Attachment = typeof attachments.$inferSelect;
export type NewAttachment = typeof attachments.$inferInsert;

export type AssetRequirement = typeof assetRequirements.$inferSelect;
export type NewAssetRequirement = typeof assetRequirements.$inferInsert;

export type ProjectReference = typeof projectReferences.$inferSelect;
export type NewProjectReference = typeof projectReferences.$inferInsert;

export type Milestone = typeof milestones.$inferSelect;
export type NewMilestone = typeof milestones.$inferInsert;

export type ReleaseCycle = typeof releaseCycles.$inferSelect;
export type NewReleaseCycle = typeof releaseCycles.$inferInsert;

export type ReleaseRequirement = typeof releaseRequirements.$inferSelect;
export type NewReleaseRequirement = typeof releaseRequirements.$inferInsert;

export type ReleaseTeamAssignment = typeof releaseTeamAssignments.$inferSelect;
export type NewReleaseTeamAssignment = typeof releaseTeamAssignments.$inferInsert;

export type ActivityLog = typeof activityLogs.$inferSelect;
export type NewActivityLog = typeof activityLogs.$inferInsert;

export type TeamInvite = typeof teamInvites.$inferSelect;
export type NewTeamInvite = typeof teamInvites.$inferInsert;

export type DiscordNotification = typeof discordNotifications.$inferSelect;
export type NewDiscordNotification = typeof discordNotifications.$inferInsert;

// Enum type exports
export type OrgRole = (typeof orgRoleEnum.enumValues)[number];
export type JobRole = (typeof jobRoleEnum.enumValues)[number];
export type ProjectRole = (typeof projectRoleEnum.enumValues)[number];
export type ProjectStatus = (typeof projectStatusEnum.enumValues)[number];
export type UpdateStatus = (typeof updateStatusEnum.enumValues)[number];
export type ItemStatus = (typeof itemStatusEnum.enumValues)[number];
export type Priority = (typeof priorityEnum.enumValues)[number];
export type ItemType = (typeof itemTypeEnum.enumValues)[number];
export type SubtaskType = (typeof subtaskTypeEnum.enumValues)[number];
export type AttachmentType = (typeof attachmentTypeEnum.enumValues)[number];
export type ActivityType = (typeof activityTypeEnum.enumValues)[number];
export type ReleaseType = (typeof releaseTypeEnum.enumValues)[number];
export type ReleaseStatus = (typeof releaseStatusEnum.enumValues)[number];
export type AssetType = (typeof assetTypeEnum.enumValues)[number];
export type AssetStatus = (typeof assetStatusEnum.enumValues)[number];
export type DocumentStatus = (typeof documentStatusEnum.enumValues)[number];

// Finance enum type exports
export type Currency = (typeof currencyEnum.enumValues)[number];
export type TransactionCategory = (typeof transactionCategoryEnum.enumValues)[number];
export type TransactionType = (typeof transactionTypeEnum.enumValues)[number];
export type PaymentMethod = (typeof paymentMethodEnum.enumValues)[number];

export type Document = typeof documents.$inferSelect;
export type NewDocument = typeof documents.$inferInsert;
export type InsertDocument = z.infer<typeof insertDocumentSchema>;

export type DocumentLink = typeof documentLinks.$inferSelect;
export type NewDocumentLink = typeof documentLinks.$inferInsert;

// Document with relations
export interface DocumentWithMeta extends Document {
  incomingLinkCount: number;
  childCount: number;
  createdBy?: SafeUser | null;
  lastEditedBy?: SafeUser | null;
}

export interface DocumentTreeNode {
  id: string;
  title: string;
  icon: string | null;
  parentId: string | null;
  sortOrder: number;
  status: DocumentStatus;
  incomingLinkCount: number;
  children: DocumentTreeNode[];
}

export interface DocumentWithLinks extends Document {
  createdBy: SafeUser | null;
  lastEditedBy: SafeUser | null;
  backlinks: { id: string; title: string; icon: string | null }[];
}

/**
 * Lightweight document data for embedding (excludes backlinks and user data)
 */
export interface EmbeddedDocumentResponse {
  id: string;
  title: string;
  icon: string | null;
  content: TipTapDocument | null;
  updatedAt: Date;
}

// ============================================
// FINANCE TYPE EXPORTS
// ============================================

export type FinanceTransaction = typeof financeTransactions.$inferSelect;
export type NewFinanceTransaction = typeof financeTransactions.$inferInsert;
export type InsertFinanceTransaction = z.infer<typeof insertFinanceTransactionSchema>;

export type ProjectBudget = typeof projectBudgets.$inferSelect;
export type NewProjectBudget = typeof projectBudgets.$inferInsert;
export type InsertProjectBudget = z.infer<typeof insertProjectBudgetSchema>;

// Extended types for API responses
export interface FinanceTransactionWithUser extends FinanceTransaction {
  createdBy: SafeUser | null;
  project?: { id: string; name: string } | null;
}

export interface ProjectBudgetWithSpend extends ProjectBudget {
  totalSpent: number;
  remainingBudget: number;
  percentUsed: number;
  isOverBudget: boolean;
  isNearThreshold: boolean;
}

export interface CategorySpendingSummary {
  category: TransactionCategory;
  currency: Currency;
  budget: number | null;
  spent: number;
  remaining: number | null;
  percentUsed: number | null;
}

export interface FinanceSummary {
  totalIncome: { robux: number; usd: number };
  totalExpenses: { robux: number; usd: number };
  netBalance: { robux: number; usd: number };
  transactionCount: number;
  byCategory: CategorySpendingSummary[];
}

// ============================================
// GAME REVENUE ANALYTICS ENUMS
// ============================================

export const gameStatusEnum = pgEnum("game_status", [
  "in_development",
  "soft_launch",
  "released",
  "sunset",
  "archived",
]);

export const revenueSourceEnum = pgEnum("revenue_source", [
  "game_pass",
  "developer_product",
  "subscription",
  "premium_payouts",
  "engagement_payouts",
  "immersive_ads",
  "other",
]);

// ============================================
// GAMES TABLE
// ============================================

export const games = pgTable(
  "games",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    projectId: varchar("project_id").references(() => projects.id, {
      onDelete: "cascade",
    }),

    // Roblox identifiers
    universeId: text("universe_id").notNull().unique(),
    rootPlaceId: text("root_place_id"),
    placeIds: jsonb("place_ids").$type<string[]>().default(sql`'[]'::jsonb`),

    // Game metadata
    name: text("name").notNull(),
    description: text("description"),
    iconUrl: text("icon_url"),
    status: gameStatusEnum("status").default("in_development").notNull(),

    // Analytics configuration
    profitCalculationMethod: text("profit_calculation_method").default(
      "method_a"
    ),
    revenueTrackingEnabled: boolean("revenue_tracking_enabled")
      .default(true)
      .notNull(),
    lastRevenueSync: timestamp("last_revenue_sync"),

    // Audit fields
    createdById: varchar("created_by_id")
      .references(() => users.id)
      .notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => ({
    projectIdx: index("games_project_idx").on(table.projectId),
    universeIdx: index("games_universe_idx").on(table.universeId),
    statusIdx: index("games_status_idx").on(table.status),
  })
);

// ============================================
// GAME REVENUE SHARES TABLE
// ============================================

export const gameRevenueShares = pgTable(
  "game_revenue_shares",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),

    // Stakeholder info
    stakeholderType: text("stakeholder_type").notNull(),
    stakeholderName: text("stakeholder_name").notNull(),
    stakeholderUserId: varchar("stakeholder_user_id").references(
      () => users.id
    ),

    // Share percentage (stored as basis points: 3300 = 33.00%)
    sharePercentage: integer("share_percentage").notNull(),

    // Time bounds
    effectiveFrom: timestamp("effective_from").notNull(),
    effectiveTo: timestamp("effective_to"),

    // Change tracking
    previousShareId: varchar("previous_share_id"),
    changeReason: text("change_reason").notNull(),

    // Audit
    createdById: varchar("created_by_id")
      .references(() => users.id)
      .notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => ({
    gameTimeIdx: index("game_revenue_shares_game_time_idx").on(
      table.gameId,
      table.effectiveFrom,
      table.effectiveTo
    ),
  })
);

// ============================================
// GAME REVENUE TABLE
// ============================================

export const gameRevenue = pgTable(
  "game_revenue",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),

    // Time
    date: timestamp("date").notNull(),

    // Revenue data
    revenue: integer("revenue").notNull(),
    currency: currencyEnum("currency").notNull(),
    source: revenueSourceEnum("source").default("other").notNull(),

    // Conversion rate for historical accuracy
    robuxUsdRate: integer("robux_usd_rate"),

    // Data provenance
    dataSource: text("data_source").default("roblox_api"),
    verified: boolean("verified").default(false).notNull(),
    verifiedById: varchar("verified_by_id").references(() => users.id),
    verifiedAt: timestamp("verified_at"),

    // Audit
    createdById: varchar("created_by_id")
      .references(() => users.id)
      .notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => ({
    gameDateIdx: index("game_revenue_game_date_idx").on(
      table.gameId,
      table.date
    ),
    currencyIdx: index("game_revenue_currency_idx").on(table.currency),
    sourceIdx: index("game_revenue_source_idx").on(table.source),
    uniqueDateCurrencySource: unique("game_revenue_unique_idx").on(
      table.gameId,
      table.date,
      table.currency,
      table.source
    ),
  })
);

// ============================================
// GAME METRICS TABLE
// ============================================

export const gameMetrics = pgTable(
  "game_metrics",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    date: timestamp("date").notNull(),

    // Player metrics
    dailyActiveUsers: integer("daily_active_users"),
    monthlyActiveUsers: integer("monthly_active_users"),
    newUsers: integer("new_users"),
    returningUsers: integer("returning_users"),

    // Engagement
    totalVisits: integer("total_visits"),
    averageSessionLength: integer("average_session_length"),
    totalPlaytime: integer("total_playtime"),

    // Monetization
    payingUsers: integer("paying_users"),
    totalTransactions: integer("total_transactions"),
    averageRevenuePerUser: integer("average_revenue_per_user"),

    // Retention (basis points: 7500 = 75.00%)
    day1Retention: integer("day1_retention"),
    day7Retention: integer("day7_retention"),
    day30Retention: integer("day30_retention"),

    // Platform
    likeRatio: integer("like_ratio"),
    favoriteCount: integer("favorite_count"),

    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => ({
    gameDateIdx: index("game_metrics_game_date_idx").on(
      table.gameId,
      table.date
    ),
    uniqueGameDate: unique("game_metrics_unique_idx").on(
      table.gameId,
      table.date
    ),
  })
);

// ============================================
// GAME DEVELOPMENT COSTS TABLE
// ============================================

export const gameDevelopmentCosts = pgTable(
  "game_development_costs",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),

    // Link to existing finance system
    transactionId: varchar("transaction_id").references(
      () => financeTransactions.id
    ),

    // Cost details
    category: transactionCategoryEnum("category").notNull(),
    amount: integer("amount").notNull(),
    currency: currencyEnum("currency").notNull(),
    description: text("description").notNull(),

    // Cost classification
    costType: text("cost_type").notNull(),
    phase: text("phase").notNull(),

    // Accounting
    capitalized: boolean("capitalized").default(false).notNull(),
    amortizationPeriod: integer("amortization_period"),

    incurredDate: timestamp("incurred_date").notNull(),

    // Audit
    createdById: varchar("created_by_id")
      .references(() => users.id)
      .notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    deletedAt: timestamp("deleted_at"),
  },
  (table) => ({
    gameIdx: index("game_dev_costs_game_idx").on(table.gameId),
    categoryIdx: index("game_dev_costs_category_idx").on(table.category),
    dateIdx: index("game_dev_costs_date_idx").on(table.incurredDate),
    phaseIdx: index("game_dev_costs_phase_idx").on(table.phase),
  })
);

// ============================================
// GAME RELATIONS
// ============================================

export const gamesRelations = relations(games, ({ one, many }) => ({
  project: one(projects, {
    fields: [games.projectId],
    references: [projects.id],
  }),
  createdBy: one(users, {
    fields: [games.createdById],
    references: [users.id],
  }),
  revenueShares: many(gameRevenueShares),
  revenue: many(gameRevenue),
  metrics: many(gameMetrics),
  developmentCosts: many(gameDevelopmentCosts),
}));

export const gameRevenueSharesRelations = relations(
  gameRevenueShares,
  ({ one }) => ({
    game: one(games, {
      fields: [gameRevenueShares.gameId],
      references: [games.id],
    }),
    stakeholderUser: one(users, {
      fields: [gameRevenueShares.stakeholderUserId],
      references: [users.id],
    }),
    createdBy: one(users, {
      fields: [gameRevenueShares.createdById],
      references: [users.id],
    }),
  })
);

export const gameRevenueRelations = relations(gameRevenue, ({ one }) => ({
  game: one(games, {
    fields: [gameRevenue.gameId],
    references: [games.id],
  }),
  verifiedBy: one(users, {
    fields: [gameRevenue.verifiedById],
    references: [users.id],
  }),
  createdBy: one(users, {
    fields: [gameRevenue.createdById],
    references: [users.id],
  }),
}));

export const gameMetricsRelations = relations(gameMetrics, ({ one }) => ({
  game: one(games, {
    fields: [gameMetrics.gameId],
    references: [games.id],
  }),
}));

export const gameDevelopmentCostsRelations = relations(
  gameDevelopmentCosts,
  ({ one }) => ({
    game: one(games, {
      fields: [gameDevelopmentCosts.gameId],
      references: [games.id],
    }),
    transaction: one(financeTransactions, {
      fields: [gameDevelopmentCosts.transactionId],
      references: [financeTransactions.id],
    }),
    createdBy: one(users, {
      fields: [gameDevelopmentCosts.createdById],
      references: [users.id],
    }),
  })
);

// ============================================
// GAME ZOD VALIDATION SCHEMAS
// ============================================

export const insertGameSchema = createInsertSchema(games, {
  universeId: z.string().min(1, "Universe ID required"),
  name: z.string().min(1).max(100),
  profitCalculationMethod: z
    .enum(["method_a", "method_b"])
    .default("method_a"),
  placeIds: z.array(z.string()).default([]),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  createdById: true,
});

export const updateGameSchema = insertGameSchema.partial();

export const insertRevenueShareSchema = createInsertSchema(gameRevenueShares, {
  sharePercentage: z
    .number()
    .int()
    .min(0)
    .max(10000, "Cannot exceed 100%"),
  effectiveFrom: z.coerce.date(),
  effectiveTo: z.coerce.date().optional().nullable(),
  changeReason: z.enum([
    "sale",
    "buyout",
    "renegotiation",
    "initial",
    "adjustment",
  ]),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  createdById: true,
});

export const updateRevenueShareSchema = insertRevenueShareSchema.partial();

export const insertGameRevenueSchema = createInsertSchema(gameRevenue, {
  revenue: z.number().int().nonnegative(),
  date: z.coerce.date(),
}).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  createdById: true,
});

export const bulkInsertGameRevenueSchema = z.object({
  importBatchId: z.string().uuid(),
  entries: z.array(insertGameRevenueSchema).min(1).max(1000),
});

export const insertGameMetricsSchema = createInsertSchema(gameMetrics).omit({
  id: true,
  createdAt: true,
});

export const insertGameDevelopmentCostSchema = createInsertSchema(
  gameDevelopmentCosts
).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  createdById: true,
});

export const profitAnalysisQuerySchema = z
  .object({
    startDate: z.coerce.date(),
    endDate: z.coerce.date(),
    currency: z.enum(["robux", "usd"]).optional(),
    granularity: z.enum(["daily", "weekly", "monthly", "total"]).default("total"),
  })
  .refine((data) => data.startDate <= data.endDate, {
    message: "Start date must be before end date",
  });

// ============================================
// GAME TYPE EXPORTS
// ============================================

export type GameStatus = (typeof gameStatusEnum.enumValues)[number];
export type RevenueSource = (typeof revenueSourceEnum.enumValues)[number];

export type Game = typeof games.$inferSelect;
export type NewGame = typeof games.$inferInsert;
export type InsertGame = z.infer<typeof insertGameSchema>;
export type UpdateGame = z.infer<typeof updateGameSchema>;

export type GameRevenueShare = typeof gameRevenueShares.$inferSelect;
export type NewGameRevenueShare = typeof gameRevenueShares.$inferInsert;
export type InsertGameRevenueShare = z.infer<typeof insertRevenueShareSchema>;

export type GameRevenue = typeof gameRevenue.$inferSelect;
export type NewGameRevenue = typeof gameRevenue.$inferInsert;
export type InsertGameRevenue = z.infer<typeof insertGameRevenueSchema>;

export type GameMetrics = typeof gameMetrics.$inferSelect;
export type NewGameMetrics = typeof gameMetrics.$inferInsert;
export type InsertGameMetrics = z.infer<typeof insertGameMetricsSchema>;

export type GameDevelopmentCost = typeof gameDevelopmentCosts.$inferSelect;
export type NewGameDevelopmentCost = typeof gameDevelopmentCosts.$inferInsert;
export type InsertGameDevelopmentCost = z.infer<
  typeof insertGameDevelopmentCostSchema
>;

// Extended types for API responses
export interface GameWithRelations extends Game {
  project?: { id: string; name: string } | null;
  createdBy: SafeUser | null;
  currentRevenueShare?: number;
}

export interface GameRevenueShareWithUser extends GameRevenueShare {
  stakeholderUser: SafeUser | null;
  createdBy: SafeUser | null;
}

export interface GameProfitAnalysis {
  gameId: string;
  dateRange: { start: Date; end: Date };
  currency: Currency;

  grossRevenue: {
    totalRevenue: number;     // Raw game revenue (before ownership %)
    amount: number;           // Revenue × Ownership%
    ownershipPercent: number; // Display as percentage (e.g., 33.00)
    formula: string;
  };

  netProfit: {
    amount: number;           // Gross Revenue - Dev Costs
    totalDevCosts: number;
    profitMargin: number;     // (Net Profit / Gross Revenue) × 100
    roi: number;              // (Net Profit / Dev Costs) × 100
    formula: string;
  };

  breakEvenPoint: {
    achieved: boolean;
    date: Date | null;
    daysToBreakEven: number | null;
  };

  ownershipHistory?: Array<{
    effectiveFrom: Date;
    effectiveTo: Date | null;
    sharePercentage: number;
  }>;
}

export interface GameMetricsSummary {
  gameId: string;
  dateRange: { start: Date; end: Date };
  averageDailyActiveUsers: number;
  peakDailyActiveUsers: number;
  totalVisits: number;
  totalPlaytime: number;
  averageSessionLength: number;
  payingUserRate: number;
  arpu: number;
}

export interface GameQueryOptions {
  search?: string;
  status?: GameStatus;
  projectId?: string;
  projectIds?: string[]; // Filter by multiple projects (for non-admin users)
  page?: number;
  limit?: number;
  offset?: number;
}

export interface RevenueQueryOptions {
  startDate?: Date;
  endDate?: Date;
  currency?: Currency;
  source?: RevenueSource;
  granularity?: "daily" | "weekly" | "monthly";
}

export interface MetricsQueryOptions {
  startDate?: Date;
  endDate?: Date;
}

export interface CostQueryOptions {
  startDate?: Date;
  endDate?: Date;
  category?: TransactionCategory;
  costType?: "one_time" | "recurring" | "variable";
  phase?: "pre_production" | "production" | "post_launch" | "ongoing";
}

export interface ProfitAnalysisOptions {
  startDate: Date;
  endDate: Date;
  currency?: Currency;
  granularity?: "daily" | "weekly" | "monthly" | "total";
}

// ============================================
// ROBLOX OPEN CLOUD INTEGRATION
// ============================================

export const robloxApiKeys = pgTable(
  "roblox_api_keys",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Which game this key is for
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Roblox Universe ID (required for API calls)
    universeId: text("universe_id").notNull(),
    // Encrypted API key (Open Cloud API key)
    encryptedApiKey: text("encrypted_api_key").notNull(),
    // Key name for identification
    name: text("name").notNull(),
    // Permissions this key has
    permissions: jsonb("permissions").$type<string[]>().default([]),
    // Is this key active?
    isActive: boolean("is_active").default(true).notNull(),
    // Last time we successfully used this key
    lastUsedAt: timestamp("last_used_at"),
    // Last sync timestamp
    lastSyncAt: timestamp("last_sync_at"),
    // Error count (for circuit breaker)
    errorCount: integer("error_count").default(0).notNull(),
    // Created by
    createdById: varchar("created_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [
    index("roblox_api_keys_game_idx").on(table.gameId),
    index("roblox_api_keys_universe_idx").on(table.universeId),
  ]
);

export type RobloxApiKey = typeof robloxApiKeys.$inferSelect;
export type NewRobloxApiKey = typeof robloxApiKeys.$inferInsert;

// ============================================
// TELEMETRY API KEYS (for in-game SDK)
// ============================================

export const telemetryApiKeys = pgTable(
  "telemetry_api_keys",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Which game this key is for
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // The actual API key (hashed for security, plain sent once on creation)
    keyHash: text("key_hash").notNull(),
    // Key prefix for identification (first 8 chars)
    keyPrefix: text("key_prefix").notNull(),
    // Human-readable name
    name: text("name").notNull(),
    // Is this key active?
    isActive: boolean("is_active").default(true).notNull(),
    // Rate limit (events per minute)
    rateLimit: integer("rate_limit").default(1000).notNull(),
    // Last used
    lastUsedAt: timestamp("last_used_at"),
    // Usage stats
    totalEvents: integer("total_events").default(0).notNull(),
    // Created by
    createdById: varchar("created_by_id").references(() => users.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    expiresAt: timestamp("expires_at"),
  },
  (table) => [
    index("telemetry_api_keys_game_idx").on(table.gameId),
    index("telemetry_api_keys_prefix_idx").on(table.keyPrefix),
  ]
);

export type TelemetryApiKey = typeof telemetryApiKeys.$inferSelect;
export type NewTelemetryApiKey = typeof telemetryApiKeys.$inferInsert;

// ============================================
// PLAYER TELEMETRY (from in-game SDK)
// ============================================

export const playerSessions = pgTable(
  "player_sessions",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Roblox Player ID
    robloxUserId: text("roblox_user_id").notNull(),
    // Session data
    sessionStartedAt: timestamp("session_started_at").notNull(),
    sessionEndedAt: timestamp("session_ended_at"),
    // Duration in seconds (calculated on end)
    durationSeconds: integer("duration_seconds"),
    // Platform info
    platform: text("platform"), // PC, Mobile, Console, VR
    deviceType: text("device_type"),
    // Locale/region (estimated)
    locale: text("locale"),
    // Is this player's first visit?
    isFirstVisit: boolean("is_first_visit").default(false),
    // Player metadata
    isPremium: boolean("is_premium").default(false),
    // Server info
    serverId: text("server_id"),
    placeVersion: integer("place_version"),
  },
  (table) => [
    index("player_sessions_game_idx").on(table.gameId),
    index("player_sessions_player_idx").on(table.robloxUserId),
    index("player_sessions_started_idx").on(table.sessionStartedAt),
    index("player_sessions_game_date_idx").on(table.gameId, table.sessionStartedAt),
  ]
);

export type PlayerSession = typeof playerSessions.$inferSelect;
export type NewPlayerSession = typeof playerSessions.$inferInsert;

// ============================================
// CUSTOM TELEMETRY EVENTS (from in-game SDK)
// ============================================

export const telemetryEvents = pgTable(
  "telemetry_events",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Player who triggered event
    robloxUserId: text("roblox_user_id").notNull(),
    // Session this event belongs to (optional)
    sessionId: varchar("session_id").references(() => playerSessions.id, {
      onDelete: "set null",
    }),
    // Event type
    eventType: text("event_type").notNull(), // purchase, level_up, quest_complete, etc.
    eventName: text("event_name").notNull(),
    // Event data
    eventData: jsonb("event_data").$type<Record<string, unknown>>(),
    // Numeric value (for aggregation)
    numericValue: real("numeric_value"),
    // Currency value (if purchase-related)
    currencyType: text("currency_type"), // robux, in_game_currency, etc.
    currencyAmount: integer("currency_amount"),
    // Timestamp
    occurredAt: timestamp("occurred_at").notNull(),
    // Server-side timestamp for ordering
    receivedAt: timestamp("received_at").defaultNow().notNull(),
  },
  (table) => [
    index("telemetry_events_game_idx").on(table.gameId),
    index("telemetry_events_type_idx").on(table.eventType),
    index("telemetry_events_player_idx").on(table.robloxUserId),
    index("telemetry_events_occurred_idx").on(table.occurredAt),
    index("telemetry_events_game_type_date_idx").on(table.gameId, table.eventType, table.occurredAt),
  ]
);

export type TelemetryEvent = typeof telemetryEvents.$inferSelect;
export type NewTelemetryEvent = typeof telemetryEvents.$inferInsert;

// ============================================
// CSV IMPORT LOGS
// ============================================

export const csvImportTypeEnum = pgEnum("csv_import_type", [
  "premium_payouts",
  "engagement_payouts",
  "immersive_ads",
  "game_passes",
  "developer_products",
  "general_revenue",
]);

export const csvImportStatusEnum = pgEnum("csv_import_status", [
  "pending",
  "processing",
  "completed",
  "failed",
  "partial",
]);

export const csvImports = pgTable(
  "csv_imports",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Which game this import is for
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Import type
    importType: csvImportTypeEnum("import_type").notNull(),
    // Status
    status: csvImportStatusEnum("status").default("pending").notNull(),
    // Original filename
    filename: text("filename").notNull(),
    // File size
    fileSizeBytes: integer("file_size_bytes"),
    // Processing stats
    totalRows: integer("total_rows"),
    processedRows: integer("processed_rows").default(0),
    successfulRows: integer("successful_rows").default(0),
    failedRows: integer("failed_rows").default(0),
    skippedRows: integer("skipped_rows").default(0), // duplicates
    // Error details
    errors: jsonb("errors").$type<Array<{ row: number; error: string }>>(),
    // Date range of imported data
    dataStartDate: timestamp("data_start_date"),
    dataEndDate: timestamp("data_end_date"),
    // Who imported
    importedById: varchar("imported_by_id")
      .references(() => users.id, { onDelete: "set null" })
      .notNull(),
    // Timestamps
    startedAt: timestamp("started_at"),
    completedAt: timestamp("completed_at"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("csv_imports_game_idx").on(table.gameId),
    index("csv_imports_status_idx").on(table.status),
    index("csv_imports_type_idx").on(table.importType),
  ]
);

export type CsvImport = typeof csvImports.$inferSelect;
export type NewCsvImport = typeof csvImports.$inferInsert;

// ============================================
// SYNC JOBS (for Open Cloud scheduled sync)
// ============================================

export const syncJobStatusEnum = pgEnum("sync_job_status", [
  "pending",
  "running",
  "completed",
  "failed",
]);

export const syncJobs = pgTable(
  "sync_jobs",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    // Which game
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Job type
    jobType: text("job_type").notNull(), // transactions, universe_info, etc.
    // Status
    status: syncJobStatusEnum("status").default("pending").notNull(),
    // Date range being synced
    syncFromDate: timestamp("sync_from_date"),
    syncToDate: timestamp("sync_to_date"),
    // Results
    recordsFetched: integer("records_fetched").default(0),
    recordsCreated: integer("records_created").default(0),
    recordsUpdated: integer("records_updated").default(0),
    recordsSkipped: integer("records_skipped").default(0),
    // Error info
    errorMessage: text("error_message"),
    errorDetails: jsonb("error_details"),
    // Cursor for pagination (Open Cloud uses cursors)
    nextCursor: text("next_cursor"),
    // Timestamps
    startedAt: timestamp("started_at"),
    completedAt: timestamp("completed_at"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  (table) => [
    index("sync_jobs_game_idx").on(table.gameId),
    index("sync_jobs_status_idx").on(table.status),
    index("sync_jobs_type_idx").on(table.jobType),
  ]
);

export type SyncJob = typeof syncJobs.$inferSelect;
export type NewSyncJob = typeof syncJobs.$inferInsert;

// ============================================
// DAILY AGGREGATED METRICS (computed from telemetry)
// ============================================

export const dailyPlayerMetrics = pgTable(
  "daily_player_metrics",
  {
    id: varchar("id")
      .primaryKey()
      .default(sql`gen_random_uuid()`),
    gameId: varchar("game_id")
      .references(() => games.id, { onDelete: "cascade" })
      .notNull(),
    // Date (UTC)
    date: timestamp("date").notNull(),
    // Player counts
    dailyActiveUsers: integer("daily_active_users").default(0).notNull(),
    newUsers: integer("new_users").default(0).notNull(),
    returningUsers: integer("returning_users").default(0).notNull(),
    // Session stats
    totalSessions: integer("total_sessions").default(0).notNull(),
    totalPlaytimeSeconds: integer("total_playtime_seconds").default(0).notNull(),
    averageSessionSeconds: integer("average_session_seconds").default(0).notNull(),
    // Peak CCU
    peakConcurrentUsers: integer("peak_concurrent_users").default(0).notNull(),
    // Platform breakdown
    pcUsers: integer("pc_users").default(0).notNull(),
    mobileUsers: integer("mobile_users").default(0).notNull(),
    consoleUsers: integer("console_users").default(0).notNull(),
    vrUsers: integer("vr_users").default(0).notNull(),
    // Premium stats
    premiumUsers: integer("premium_users").default(0).notNull(),
    // Computed at
    computedAt: timestamp("computed_at").defaultNow().notNull(),
  },
  (table) => [
    index("daily_player_metrics_game_idx").on(table.gameId),
    index("daily_player_metrics_date_idx").on(table.date),
    // Unique constraint to prevent duplicate entries
    index("daily_player_metrics_game_date_unique").on(table.gameId, table.date),
  ]
);

export type DailyPlayerMetrics = typeof dailyPlayerMetrics.$inferSelect;
export type NewDailyPlayerMetrics = typeof dailyPlayerMetrics.$inferInsert;

// ============================================
// Zod schemas for API validation
// ============================================

export const insertRobloxApiKeySchema = z.object({
  gameId: z.string().uuid(),
  universeId: z.string().min(1, "Universe ID is required"),
  apiKey: z.string().min(1, "API key is required"),
  name: z.string().min(1, "Name is required").max(100),
  permissions: z.array(z.string()).optional(),
});

export const insertTelemetryApiKeySchema = z.object({
  gameId: z.string().uuid(),
  name: z.string().min(1, "Name is required").max(100),
  rateLimit: z.number().min(100).max(10000).optional(),
  expiresAt: z.string().datetime().optional(),
});

// Telemetry event from SDK
export const telemetryEventSchema = z.object({
  eventType: z.string().min(1).max(50),
  eventName: z.string().min(1).max(100),
  robloxUserId: z.string().min(1),
  sessionId: z.string().optional(),
  eventData: z.record(z.unknown()).optional(),
  numericValue: z.number().optional(),
  currencyType: z.string().optional(),
  currencyAmount: z.number().int().optional(),
  occurredAt: z.string().datetime(),
});

// Batch telemetry events from SDK
export const telemetryBatchSchema = z.object({
  events: z.array(telemetryEventSchema).min(1).max(100),
});

// Session start from SDK
export const sessionStartSchema = z.object({
  robloxUserId: z.string().min(1),
  platform: z.enum(["PC", "Mobile", "Console", "VR"]).optional(),
  deviceType: z.string().optional(),
  locale: z.string().optional(),
  isPremium: z.boolean().optional(),
  serverId: z.string().optional(),
  placeVersion: z.number().int().optional(),
  isFirstVisit: z.boolean().optional(),
});

// Session end from SDK
export const sessionEndSchema = z.object({
  sessionId: z.string().uuid(),
  endedAt: z.string().datetime(),
});

// CSV import schema
export const csvImportSchema = z.object({
  gameId: z.string().uuid(),
  importType: z.enum([
    "premium_payouts",
    "engagement_payouts",
    "immersive_ads",
    "game_passes",
    "developer_products",
    "general_revenue",
  ]),
});
