import { useState, useMemo } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import {
  useProjects,
  useFinanceTransactions,
  useProjectFinanceSummary,
  useProjectBudgetsWithSpending,
  useDeleteFinanceTransaction,
  type FinanceTransactionWithUser,
  type ProjectWithDetails,
  type Currency,
} from '@/hooks/useApi';
import { useAuth } from '@/contexts/AuthContext';
import {
  isAdmin,
  canAccessFinancesPage,
  canViewProjectFinances,
  canManageProjectFinances,
  canManageBudget,
  canOnlyAddExpenses,
  type ProjectMemberInfo,
} from '@/lib/permissions';
import {
  TransactionCard,
  SpendingPieChart,
  AddTransactionDialog,
  SetBudgetDialog,
  BudgetProgressBar,
  FinanceWeekSection,
  formatAmount,
  TransactionCategoryPills,
  BudgetOverviewPanel,
  TransactionLogTable,
  robuxToUsd,
  centsToRobux,
} from '@/components/finance';
import type { TransactionCategory, TransactionType } from '@/hooks/useApi';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import {
  Plus,
  Search,
  Wallet,
  DollarSign,
  Coins,
  Target,
  TrendingUp,
  TrendingDown,
  ArrowUpDown,
  ShieldAlert,
  BarChart3,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Get current ISO week number
function getCurrentWeekYear(): { week: number; year: number } {
  const now = new Date();
  const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return { week: weekNo, year: d.getUTCFullYear() };
}

// Summary stat card
function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  className,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: typeof DollarSign;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}) {
  return (
    <Card className={cn('bg-card/50 backdrop-blur-sm', className)}>
      <CardContent className="pt-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-medium">{title}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
            )}
          </div>
          <div className={cn(
            'p-2 rounded-lg',
            trend === 'up' && 'bg-emerald-500/20 text-emerald-500',
            trend === 'down' && 'bg-red-500/20 text-red-500',
            trend === 'neutral' && 'bg-muted text-muted-foreground'
          )}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Finances() {
  const { user } = useAuth();
  const { toast } = useToast();
  const { week: currentWeek, year: currentYear } = getCurrentWeekYear();

  // State
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<TransactionCategory | 'all'>('all');
  const [selectedType, setSelectedType] = useState<TransactionType | 'all'>('all');
  const [selectedCurrency, setSelectedCurrency] = useState<Currency | 'all'>('all');
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [budgetDialogOpen, setBudgetDialogOpen] = useState(false);
  const [budgetDialogCategory, setBudgetDialogCategory] = useState<TransactionCategory | undefined>();
  const [budgetDialogCurrency, setBudgetDialogCurrency] = useState<Currency | undefined>();
  const [editingTransaction, setEditingTransaction] = useState<FinanceTransactionWithUser | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('table');
  const [budgetPeriod, setBudgetPeriod] = useState<'weekly' | 'monthly'>('monthly');

  // Check access
  if (!canAccessFinancesPage(user)) {
    return (
      <AppLayout title="Finances">
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <ShieldAlert className="h-16 w-16 text-muted-foreground mb-4" />
          <h2 className="text-2xl font-bold mb-2">Access Restricted</h2>
          <p className="text-muted-foreground max-w-md">
            The Finances section is only available to Project Managers and above.
            If you believe you should have access, please contact an administrator.
          </p>
        </div>
      </AppLayout>
    );
  }

  // Fetch projects
  const { data: projectsData, isLoading: loadingProjects } = useProjects();
  const projects = projectsData?.data || [];

  // Filter projects based on user's finance access
  const accessibleProjects = useMemo(() => {
    if (isAdmin(user)) return projects;
    return projects.filter(project => {
      const members: ProjectMemberInfo[] = project.members?.map(m => ({
        userId: m.user.id,
        projectRole: m.projectRole,
      })) || [];
      return canViewProjectFinances(user, members);
    });
  }, [projects, user]);

  // Fetch transactions
  const { data: transactionsData, isLoading: loadingTransactions, refetch: refetchTransactions } = useFinanceTransactions({
    projectId: selectedProjectId !== 'all' ? selectedProjectId : undefined,
    search: searchQuery || undefined,
  });
  const transactions = transactionsData?.data || [];

  // Fetch summary for selected project
  const { data: summaryData } = useProjectFinanceSummary(
    selectedProjectId !== 'all' ? selectedProjectId : undefined
  );
  const summary = summaryData?.data;

  // Fetch budgets with spending for selected project
  const { data: budgetsData, refetch: refetchBudgets } = useProjectBudgetsWithSpending(
    selectedProjectId !== 'all' ? selectedProjectId : undefined
  );
  const budgetsWithSpending = budgetsData?.data || [];

  // Delete mutation
  const deleteTransaction = useDeleteFinanceTransaction();

  // Filter and group transactions
  const filteredTransactions = useMemo(() => {
    return transactions.filter(tx => {
      if (selectedCategory !== 'all' && tx.category !== selectedCategory) return false;
      if (selectedType !== 'all' && tx.type !== selectedType) return false;
      if (selectedCurrency !== 'all' && tx.currency !== selectedCurrency) return false;
      return true;
    });
  }, [transactions, selectedCategory, selectedType, selectedCurrency]);

  // Calculate category counts for pills
  const categoryCounts = useMemo(() => {
    const counts: Record<TransactionCategory | 'all', number> = {
      all: transactions.length,
      programming: 0,
      animation: 0,
      modeling: 0,
      vfx: 0,
      sfx: 0,
      marketing: 0,
      video_trailer: 0,
      ui: 0,
      music: 0,
      other: 0,
    };
    transactions.forEach(tx => {
      counts[tx.category]++;
    });
    return counts;
  }, [transactions]);

  // Group transactions by week
  const transactionsByWeek = useMemo(() => {
    const grouped: Record<string, FinanceTransactionWithUser[]> = {};
    filteredTransactions.forEach(tx => {
      const weekKey = `${tx.year}-W${String(tx.weekNumber).padStart(2, '0')}`;
      if (!grouped[weekKey]) {
        grouped[weekKey] = [];
      }
      grouped[weekKey].push(tx);
    });
    // Sort weeks in descending order (newest first)
    return Object.entries(grouped)
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([weekKey, txs]) => ({ weekKey, transactions: txs }));
  }, [filteredTransactions]);

  // Calculate totals for each week
  const weekTotals = useMemo(() => {
    const totals: Record<string, { robux: number; usd: number }> = {};
    transactionsByWeek.forEach(({ weekKey, transactions }) => {
      totals[weekKey] = { robux: 0, usd: 0 };
      transactions.forEach(tx => {
        const amount = tx.type === 'expense' ? -tx.amount : tx.amount;
        if (tx.currency === 'robux') {
          totals[weekKey].robux += amount;
        } else {
          totals[weekKey].usd += amount;
        }
      });
    });
    return totals;
  }, [transactionsByWeek]);

  // Get selected project info
  const selectedProject = selectedProjectId !== 'all'
    ? accessibleProjects.find(p => p.id === selectedProjectId)
    : null;

  // Check permissions for actions
  const canAddTransaction = useMemo(() => {
    if (!selectedProject) return isAdmin(user);
    const members: ProjectMemberInfo[] = selectedProject.members?.map(m => ({
      userId: m.user.id,
      projectRole: m.projectRole,
    })) || [];
    return canManageProjectFinances(user, members);
  }, [selectedProject, user]);

  const canSetBudget = useMemo(() => {
    if (!selectedProject) return false;
    const members: ProjectMemberInfo[] = selectedProject.members?.map(m => ({
      userId: m.user.id,
      projectRole: m.projectRole,
    })) || [];
    return canManageBudget(user, members);
  }, [selectedProject, user]);

  // Handle delete
  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    try {
      await deleteTransaction.mutateAsync(deleteConfirmId);
      toast({ title: 'Transaction deleted successfully' });
      refetchTransactions();
    } catch (error) {
      toast({ title: 'Failed to delete transaction', variant: 'destructive' });
    } finally {
      setDeleteConfirmId(null);
    }
  };

  // Handle edit
  const handleEdit = (transaction: FinanceTransactionWithUser) => {
    setEditingTransaction(transaction);
    setAddDialogOpen(true);
  };

  // Handle open budget dialog (optionally with category pre-selected)
  const handleOpenBudgetDialog = (category?: TransactionCategory, currency?: Currency) => {
    setBudgetDialogCategory(category);
    setBudgetDialogCurrency(currency);
    setBudgetDialogOpen(true);
  };

  // Check if user can edit/delete a specific transaction
  const canEditTransaction = (transaction: FinanceTransactionWithUser) => {
    if (isAdmin(user)) return true;
    const project = accessibleProjects.find(p => p.id === transaction.projectId);
    if (!project) return false;
    const members: ProjectMemberInfo[] = project.members?.map(m => ({
      userId: m.user.id,
      projectRole: m.projectRole,
    })) || [];

    // Project managers cannot edit/delete income transactions
    if (transaction.type === 'income' && canOnlyAddExpenses(user, members)) {
      return false;
    }

    // Creator or manager can edit expenses
    return transaction.createdById === user?.id || canManageProjectFinances(user, members);
  };

  const currentWeekKey = `${currentYear}-W${String(currentWeek).padStart(2, '0')}`;

  return (
    <AppLayout title="Finances">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Wallet className="h-6 w-6" />
              Finances
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Track expenses and budgets across your projects
            </p>
          </div>
          <div className="flex items-center gap-2">
            {canSetBudget && selectedProjectId !== 'all' && (
              <Button variant="outline" onClick={() => setBudgetDialogOpen(true)}>
                <Target className="h-4 w-4 mr-2" />
                Set Budget
              </Button>
            )}
            {canAddTransaction && (
              <Button onClick={() => {
                setEditingTransaction(null);
                setAddDialogOpen(true);
              }}>
                <Plus className="h-4 w-4 mr-2" />
                Add Transaction
              </Button>
            )}
          </div>
        </div>

        {/* Filters - Row 1: Project & Search */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="All Projects" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Projects</SelectItem>
              {accessibleProjects.map(project => (
                <SelectItem key={project.id} value={project.id}>
                  {project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search transactions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Filters - Row 2: Category Pills */}
        <TransactionCategoryPills
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          categoryCounts={categoryCounts}
        />

        {/* Filters - Row 3: Type & Currency Toggles */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Type:</span>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={selectedType === 'all' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setSelectedType('all')}
              >
                <ArrowUpDown className="h-3 w-3 mr-1" />
                All
              </Button>
              <Button
                size="sm"
                variant={selectedType === 'expense' ? 'secondary' : 'ghost'}
                className={cn('h-7 px-2.5 text-xs', selectedType === 'expense' && 'text-red-500')}
                onClick={() => setSelectedType('expense')}
              >
                Expenses
              </Button>
              <Button
                size="sm"
                variant={selectedType === 'income' ? 'secondary' : 'ghost'}
                className={cn('h-7 px-2.5 text-xs', selectedType === 'income' && 'text-emerald-500')}
                onClick={() => setSelectedType('income')}
              >
                Income
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Currency:</span>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={selectedCurrency === 'all' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setSelectedCurrency('all')}
              >
                Both
              </Button>
              <Button
                size="sm"
                variant={selectedCurrency === 'robux' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setSelectedCurrency('robux')}
              >
                <Coins className="h-3 w-3 mr-1" />
                Robux
              </Button>
              <Button
                size="sm"
                variant={selectedCurrency === 'usd' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setSelectedCurrency('usd')}
              >
                <DollarSign className="h-3 w-3 mr-1" />
                USD
              </Button>
            </div>
          </div>

          {/* Budget Period Toggle */}
          {selectedProjectId !== 'all' && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Period:</span>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant={budgetPeriod === 'weekly' ? 'secondary' : 'ghost'}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setBudgetPeriod('weekly')}
                >
                  Weekly
                </Button>
                <Button
                  size="sm"
                  variant={budgetPeriod === 'monthly' ? 'secondary' : 'ghost'}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setBudgetPeriod('monthly')}
                >
                  Monthly
                </Button>
              </div>
            </div>
          )}

          {/* View Mode Toggle */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs text-muted-foreground">View:</span>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={viewMode === 'table' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setViewMode('table')}
              >
                Table
              </Button>
              <Button
                size="sm"
                variant={viewMode === 'cards' ? 'secondary' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => setViewMode('cards')}
              >
                Cards
              </Button>
            </div>
          </div>
        </div>

        {/* Summary Cards (only when project selected) */}
        {selectedProjectId !== 'all' && summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              title="Total Robux Spent"
              value={formatAmount(summary.totalExpenses.robux, 'robux')}
              subtitle={`~$${robuxToUsd(summary.totalExpenses.robux).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              icon={Coins}
              trend="neutral"
            />
            <StatCard
              title="Total USD Spent"
              value={formatAmount(summary.totalExpenses.usd, 'usd')}
              subtitle={`~R$${centsToRobux(summary.totalExpenses.usd).toLocaleString()}`}
              icon={DollarSign}
              trend="neutral"
            />
            <StatCard
              title="Net Robux"
              value={formatAmount(summary.netBalance.robux, 'robux')}
              subtitle={`~$${robuxToUsd(Math.abs(summary.netBalance.robux)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              icon={summary.netBalance.robux >= 0 ? TrendingUp : TrendingDown}
              trend={summary.netBalance.robux >= 0 ? 'up' : 'down'}
            />
            <StatCard
              title="Net USD"
              value={formatAmount(summary.netBalance.usd, 'usd')}
              subtitle={`~R$${centsToRobux(Math.abs(summary.netBalance.usd)).toLocaleString()}`}
              icon={summary.netBalance.usd >= 0 ? TrendingUp : TrendingDown}
              trend={summary.netBalance.usd >= 0 ? 'up' : 'down'}
            />
          </div>
        )}

        {/* Budget Overview Panel (only when project selected) */}
        {selectedProjectId !== 'all' && (
          <BudgetOverviewPanel
            budgets={budgetsWithSpending}
            onSetBudget={handleOpenBudgetDialog}
            defaultExpanded={budgetsWithSpending.length > 0}
          />
        )}

        {/* Charts (only when project selected) */}
        {selectedProjectId !== 'all' && summary && summary.byCategory.length > 0 && (
          <div className="grid md:grid-cols-2 gap-4">
            <SpendingPieChart
              data={summary.byCategory}
              currency="robux"
              title="Robux Spending"
            />
            <SpendingPieChart
              data={summary.byCategory}
              currency="usd"
              title="USD Spending"
            />
          </div>
        )}

        {/* Transactions by Week */}
        {loadingTransactions ? (
          <div className="space-y-4">
            {[1, 2].map(i => (
              <Skeleton key={i} className="h-[200px] rounded-xl" />
            ))}
          </div>
        ) : transactionsByWeek.length === 0 ? (
          <Card className="bg-card/50 backdrop-blur-sm">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <BarChart3 className="h-16 w-16 text-muted-foreground mb-4 opacity-50" />
              <h3 className="text-lg font-semibold mb-2">No transactions found</h3>
              <p className="text-muted-foreground text-center max-w-md mb-4">
                {selectedProjectId === 'all'
                  ? "Start tracking your finances by adding your first transaction."
                  : "No transactions recorded for this project yet."}
              </p>
              {canAddTransaction && (
                <Button onClick={() => {
                  setEditingTransaction(null);
                  setAddDialogOpen(true);
                }}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Transaction
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {transactionsByWeek.map(({ weekKey, transactions: weekTransactions }) => {
              const totals = weekTotals[weekKey] || { robux: 0, usd: 0 };
              const isCurrentWeekSection = weekKey === currentWeekKey;
              return (
                <FinanceWeekSection
                  key={weekKey}
                  weekKey={weekKey}
                  transactionCount={weekTransactions.length}
                  totalRobux={totals.robux}
                  totalUsd={totals.usd}
                  isCurrentWeek={isCurrentWeekSection}
                  defaultExpanded={isCurrentWeekSection}
                >
                  {viewMode === 'table' ? (
                    <TransactionLogTable
                      transactions={weekTransactions}
                      onEdit={handleEdit}
                      onDelete={setDeleteConfirmId}
                      canEdit={true}
                      canDelete={true}
                      showProject={selectedProjectId === 'all'}
                    />
                  ) : (
                    <div className="space-y-2">
                      {weekTransactions.map(tx => (
                        <TransactionCard
                          key={tx.id}
                          transaction={tx}
                          showProject={selectedProjectId === 'all'}
                          canEdit={canEditTransaction(tx)}
                          canDelete={canEditTransaction(tx)}
                          onEdit={handleEdit}
                          onDelete={setDeleteConfirmId}
                        />
                      ))}
                    </div>
                  )}
                </FinanceWeekSection>
              );
            })}
          </div>
        )}
      </div>

      {/* Add/Edit Transaction Dialog */}
      <AddTransactionDialog
        open={addDialogOpen}
        onOpenChange={(open) => {
          setAddDialogOpen(open);
          if (!open) setEditingTransaction(null);
        }}
        projects={accessibleProjects.map(p => ({
          id: p.id,
          name: p.name,
          members: p.members?.map(m => ({
            user: { id: m.user.id },
            projectRole: m.projectRole,
          })),
        }))}
        defaultProjectId={selectedProjectId !== 'all' ? selectedProjectId : undefined}
        editingTransaction={editingTransaction}
        onSuccess={() => {
          refetchTransactions();
          refetchBudgets();
        }}
      />

      {/* Set Budget Dialog */}
      {selectedProject && (
        <SetBudgetDialog
          open={budgetDialogOpen}
          onOpenChange={setBudgetDialogOpen}
          projectId={selectedProject.id}
          projectName={selectedProject.name}
          onSuccess={() => refetchBudgets()}
        />
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Transaction</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this transaction? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  );
}
