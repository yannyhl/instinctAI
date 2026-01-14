import { type FC, useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { canOnlyAddExpenses, type ProjectMemberInfo } from '@/lib/permissions';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useToast } from '@/hooks/use-toast';
import {
  useCreateFinanceTransaction,
  useUpdateFinanceTransaction,
  type TransactionCategory,
  type Currency,
  type TransactionType,
  type PaymentMethod,
  type FinanceTransactionWithUser,
} from '@/hooks/useApi';
import { CATEGORY_CONFIG, robuxToUsd, usdToRobux } from './TransactionCard';
import { Loader2, Upload, X, DollarSign, Coins, Plus, Receipt, ArrowRight } from 'lucide-react';
import { format } from 'date-fns';

// Get current ISO week and year
function getCurrentWeekYear(): { week: number; year: number } {
  const now = new Date();
  const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return { week: weekNo, year: d.getUTCFullYear() };
}

const CATEGORIES: TransactionCategory[] = [
  'programming', 'animation', 'modeling', 'vfx', 'sfx',
  'marketing', 'video_trailer', 'ui', 'music', 'other'
];

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'robux_direct', label: 'Robux Direct' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'paypal', label: 'PayPal' },
  { value: 'other', label: 'Other' },
];

interface ProjectWithMembers {
  id: string;
  name: string;
  members?: { user: { id: string }; projectRole: string }[];
}

interface AddTransactionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projects: ProjectWithMembers[];
  defaultProjectId?: string;
  editingTransaction?: FinanceTransactionWithUser | null;
  onSuccess?: () => void;
  /**
   * When true, forces expense-only mode regardless of project selection.
   * When false or undefined, expense-only is calculated dynamically based on selected project.
   */
  expenseOnly?: boolean;
}

export const AddTransactionDialog: FC<AddTransactionDialogProps> = ({
  open,
  onOpenChange,
  projects,
  defaultProjectId,
  editingTransaction,
  onSuccess,
  expenseOnly: expenseOnlyProp,
}) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const createTransaction = useCreateFinanceTransaction();
  const updateTransaction = useUpdateFinanceTransaction();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { week: currentWeek, year: currentYear } = getCurrentWeekYear();

  // Form state
  const [projectId, setProjectId] = useState(defaultProjectId || '');
  const [type, setType] = useState<TransactionType>('expense');
  const [category, setCategory] = useState<TransactionCategory>('programming');
  const [currency, setCurrency] = useState<Currency>('robux');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [payeeName, setPayeeName] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('robux_direct');
  const [weekNumber, setWeekNumber] = useState(currentWeek);
  const [year, setYear] = useState(currentYear);
  const [transactionDate, setTransactionDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [receiptUrl, setReceiptUrl] = useState('');
  const [uploading, setUploading] = useState(false);

  // Calculate expenseOnly dynamically based on selected project
  // If expenseOnlyProp is explicitly true, always use it
  // Otherwise, calculate based on the selected project's membership
  const expenseOnly = useMemo(() => {
    // If prop is explicitly true, force expense-only
    if (expenseOnlyProp === true) return true;

    // If no project selected, default to expense-only for safety
    if (!projectId) return true;

    // Find the selected project and check membership
    const selectedProject = projects.find(p => p.id === projectId);
    if (!selectedProject?.members) return true;

    const members: ProjectMemberInfo[] = selectedProject.members.map(m => ({
      userId: m.user.id,
      projectRole: m.projectRole,
    }));

    return canOnlyAddExpenses(user, members);
  }, [expenseOnlyProp, projectId, projects, user]);

  // Reset form when dialog opens/closes or editing changes
  useEffect(() => {
    if (open) {
      if (editingTransaction) {
        // Populate form with existing data
        setProjectId(editingTransaction.projectId);
        setType(editingTransaction.type);
        setCategory(editingTransaction.category);
        setCurrency(editingTransaction.currency);
        setAmount(editingTransaction.currency === 'usd'
          ? (editingTransaction.amount / 100).toString()
          : editingTransaction.amount.toString()
        );
        setDescription(editingTransaction.description || '');
        setPayeeName(editingTransaction.payeeName || '');
        setPaymentMethod(editingTransaction.paymentMethod);
        setWeekNumber(editingTransaction.weekNumber);
        setYear(editingTransaction.year);
        setTransactionDate(format(new Date(editingTransaction.transactionDate), 'yyyy-MM-dd'));
        setReceiptUrl(editingTransaction.receiptUrl || '');
      } else {
        // Reset to defaults
        setProjectId(defaultProjectId || '');
        setType('expense'); // Always default to expense
        setCategory('programming');
        setCurrency('robux');
        setAmount('');
        setDescription('');
        setPayeeName('');
        setPaymentMethod('robux_direct');
        setWeekNumber(currentWeek);
        setYear(currentYear);
        setTransactionDate(format(new Date(), 'yyyy-MM-dd'));
        setReceiptUrl('');
      }
    }
  }, [open, editingTransaction, defaultProjectId, currentWeek, currentYear]);

  // Force type to 'expense' when expenseOnly becomes true (e.g., user selects different project)
  useEffect(() => {
    if (expenseOnly && type === 'income') {
      setType('expense');
    }
  }, [expenseOnly, type]);

  // Update payment method based on currency
  useEffect(() => {
    if (currency === 'robux') {
      setPaymentMethod('robux_direct');
    } else if (paymentMethod === 'robux_direct') {
      setPaymentMethod('bank_transfer');
    }
  }, [currency, paymentMethod]);

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('projectId', projectId);
      formData.append('name', `receipt-${Date.now()}`);
      formData.append('type', 'file');
      formData.append('category', 'reference');

      const response = await fetch('/api/uploads/file', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();
      if (result.success && result.data?.url) {
        setReceiptUrl(result.data.url);
        toast({
          title: 'Receipt uploaded',
          description: 'Your receipt has been attached to this transaction.',
        });
      }
    } catch (error) {
      toast({
        title: 'Upload failed',
        description: 'Failed to upload receipt. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (!projectId) {
      toast({ title: 'Please select a project', variant: 'destructive' });
      return;
    }
    if (!amount || parseFloat(amount) <= 0) {
      toast({ title: 'Please enter a valid amount', variant: 'destructive' });
      return;
    }

    // Convert amount to integer (cents for USD, raw for Robux)
    let amountInt = Math.round(parseFloat(amount));
    if (currency === 'usd') {
      amountInt = Math.round(parseFloat(amount) * 100);
    }

    try {
      if (editingTransaction) {
        await updateTransaction.mutateAsync({
          id: editingTransaction.id,
          data: {
            type,
            category,
            currency,
            amount: amountInt,
            description: description || undefined,
            payeeName: payeeName || undefined,
            paymentMethod,
            weekNumber,
            year,
            transactionDate: new Date(transactionDate).toISOString(),
            receiptUrl: receiptUrl || undefined,
          },
        });
        toast({ title: 'Transaction updated successfully' });
      } else {
        await createTransaction.mutateAsync({
          projectId,
          type,
          category,
          currency,
          amount: amountInt,
          description: description || undefined,
          payeeName: payeeName || undefined,
          paymentMethod,
          weekNumber,
          year,
          transactionDate: new Date(transactionDate).toISOString(),
          receiptUrl: receiptUrl || undefined,
        });
        toast({ title: 'Transaction created successfully' });
      }
      onOpenChange(false);
      onSuccess?.();
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.message || 'Failed to save transaction',
        variant: 'destructive',
      });
    }
  };

  const isLoading = createTransaction.isPending || updateTransaction.isPending;

  // Calculate converted amount in real-time
  const convertedAmount = useMemo(() => {
    const numAmount = parseFloat(amount);
    if (!amount || isNaN(numAmount) || numAmount <= 0) return null;

    if (currency === 'robux') {
      const usdValue = robuxToUsd(numAmount);
      return {
        value: usdValue,
        display: `~$${usdValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        label: 'USD equivalent',
      };
    } else {
      const robuxValue = usdToRobux(numAmount);
      return {
        value: robuxValue,
        display: `~R$${robuxValue.toLocaleString()}`,
        label: 'Robux equivalent',
      };
    }
  }, [amount, currency]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {editingTransaction ? (
              <>Edit Transaction</>
            ) : (
              <>
                <Plus className="h-5 w-5" />
                Add Transaction
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {editingTransaction
              ? 'Update the transaction details below.'
              : expenseOnly
                ? 'Record a new expense transaction for developer payments.'
                : 'Record a new expense or income transaction.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Project Selection */}
          {!editingTransaction && (
            <div className="grid gap-2">
              <Label htmlFor="project">Project</Label>
              <Select value={projectId} onValueChange={setProjectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map(project => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Type Selection - Hide income option for project managers (expenseOnly mode) */}
          <div className="grid gap-2">
            <Label>Transaction Type</Label>
            {expenseOnly ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">Expense</span>
                <span className="text-xs">(Project managers can only add expenses)</span>
              </div>
            ) : (
              <RadioGroup
                value={type}
                onValueChange={(v) => setType(v as TransactionType)}
                className="flex gap-4"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="expense" id="expense" />
                  <Label htmlFor="expense" className="font-normal cursor-pointer">Expense</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="income" id="income" />
                  <Label htmlFor="income" className="font-normal cursor-pointer">Income</Label>
                </div>
              </RadioGroup>
            )}
          </div>

          {/* Currency and Amount */}
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label>Currency</Label>
              <RadioGroup
                value={currency}
                onValueChange={(v) => setCurrency(v as Currency)}
                className="flex gap-4"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="robux" id="robux" />
                  <Label htmlFor="robux" className="font-normal cursor-pointer flex items-center gap-1">
                    <Coins className="h-3.5 w-3.5" />
                    Robux
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="usd" id="usd" />
                  <Label htmlFor="usd" className="font-normal cursor-pointer flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5" />
                    USD
                  </Label>
                </div>
              </RadioGroup>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="amount">Amount</Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                  {currency === 'robux' ? 'R$' : '$'}
                </span>
                <Input
                  id="amount"
                  type="number"
                  step={currency === 'usd' ? '0.01' : '1'}
                  min="0"
                  placeholder="0"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="pl-9"
                />
              </div>
              {/* Real-time conversion display */}
              {convertedAmount && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
                  <ArrowRight className="h-3 w-3" />
                  <span className="font-medium text-foreground">{convertedAmount.display}</span>
                  <span>({convertedAmount.label})</span>
                </div>
              )}
            </div>
          </div>

          {/* Category */}
          <div className="grid gap-2">
            <Label htmlFor="category">Category</Label>
            <Select value={category} onValueChange={(v) => setCategory(v as TransactionCategory)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map(cat => (
                  <SelectItem key={cat} value={cat}>
                    <span className={CATEGORY_CONFIG[cat].color}>
                      {CATEGORY_CONFIG[cat].label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Payee Name */}
          <div className="grid gap-2">
            <Label htmlFor="payee">Payee Name</Label>
            <Input
              id="payee"
              placeholder="Who received the payment?"
              value={payeeName}
              onChange={(e) => setPayeeName(e.target.value)}
            />
          </div>

          {/* Payment Method */}
          <div className="grid gap-2">
            <Label htmlFor="payment-method">Payment Method</Label>
            <Select value={paymentMethod} onValueChange={(v) => setPaymentMethod(v as PaymentMethod)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAYMENT_METHODS
                  .filter(pm => currency === 'robux' ? pm.value === 'robux_direct' : pm.value !== 'robux_direct')
                  .map(pm => (
                    <SelectItem key={pm.value} value={pm.value}>
                      {pm.label}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date, Week, Year */}
          <div className="grid grid-cols-3 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
                type="date"
                value={transactionDate}
                onChange={(e) => setTransactionDate(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="week">Week</Label>
              <Input
                id="week"
                type="number"
                min="1"
                max="53"
                value={weekNumber}
                onChange={(e) => setWeekNumber(parseInt(e.target.value) || 1)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="year">Year</Label>
              <Input
                id="year"
                type="number"
                min="2020"
                max="2100"
                value={year}
                onChange={(e) => setYear(parseInt(e.target.value) || currentYear)}
              />
            </div>
          </div>

          {/* Description */}
          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Optional description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>

          {/* Receipt Upload */}
          <div className="grid gap-2">
            <Label>Receipt / Invoice</Label>
            {receiptUrl ? (
              <div className="flex items-center gap-2 p-2 rounded-lg border bg-muted/50">
                <Receipt className="h-4 w-4 text-emerald-500" />
                <span className="text-sm text-emerald-500 flex-1 truncate">Receipt attached</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => setReceiptUrl('')}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileUpload(file);
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading || !projectId}
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  {uploading ? 'Uploading...' : 'Upload Receipt'}
                </Button>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading}>
            {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {editingTransaction ? 'Update' : 'Add Transaction'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AddTransactionDialog;
