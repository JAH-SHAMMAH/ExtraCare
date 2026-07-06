"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { financeApi } from "@/lib/api";
import type {
  LedgerAccount, AccountingPeriod, FinanceInvoice, PayrollRun,
  Budget, PettyCashTxn, CashTransaction, StoreItem, Paginated,
  FinancialStatements, SalaryAdvance, PayAdjustmentPack, Requisition, IncomeExpenseReport, FeeDiscount,
  FeeRecord, ClassFeeAssignResult, ClassOption, BankAccount, BankAccountPublic, FinanceSettings, StoreSale, StoreSalesSummary, PaymentGateway,
  Warehouse, WarehouseStockRow, PickupPoint, Pickup,
} from "@/types";

function invalidate(qc: ReturnType<typeof useQueryClient>, keys: string[]) {
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

// ── Chart of Accounts ───────────────────────────────────────────────────────────

export function useAccounts(params?: { type?: string; active_only?: boolean }) {
  return useQuery<LedgerAccount[]>({ queryKey: ["accounts", params], queryFn: () => financeApi.accounts.list(params) });
}
export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.accounts.create(data),
    onSuccess: () => { invalidate(qc, ["accounts"]); toast.success("Account created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create account."),
  });
}
export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.accounts.update(id, data),
    onSuccess: () => { invalidate(qc, ["accounts"]); toast.success("Account updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.accounts.remove(id),
    onSuccess: () => { invalidate(qc, ["accounts"]); toast.success("Account removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Accounting Periods ──────────────────────────────────────────────────────────

export function usePeriods() {
  return useQuery<AccountingPeriod[]>({ queryKey: ["periods"], queryFn: () => financeApi.periods.list() });
}
export function useCreatePeriod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.periods.create(data),
    onSuccess: () => { invalidate(qc, ["periods"]); toast.success("Period created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create period."),
  });
}
export function useLockPeriod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, lock }: { id: string; lock: boolean }) => (lock ? financeApi.periods.lock(id) : financeApi.periods.unlock(id)),
    onSuccess: (_d, v) => { invalidate(qc, ["periods"]); toast.success(v.lock ? "Period locked." : "Period unlocked."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to change lock."),
  });
}

// ── Journal (Direct Posts / Direct Transfer) & Financial Statements ──────────────

export function useStatements(params?: { as_of?: string }) {
  return useQuery<FinancialStatements>({ queryKey: ["statements", params], queryFn: () => financeApi.statements(params) });
}
export function useJournal(params?: { page?: number; page_size?: number }) {
  return useQuery<Paginated<any>>({ queryKey: ["journal", params], queryFn: () => financeApi.journal.list(params) });
}
export function usePostJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.journal.post(data),
    onSuccess: () => { invalidate(qc, ["statements", "journal", "accounts"]); toast.success("Posted to the ledger."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to post entry."),
  });
}

// ── Invoices ────────────────────────────────────────────────────────────────────

export function useInvoices(params?: { status?: string }) {
  return useQuery<Paginated<FinanceInvoice>>({ queryKey: ["invoices", params], queryFn: () => financeApi.invoices.list(params) });
}
export function useCreateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.invoices.create(data),
    onSuccess: () => { invalidate(qc, ["invoices"]); toast.success("Invoice drafted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to draft invoice."),
  });
}
export function useDeleteInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.invoices.remove(id),
    onSuccess: () => { invalidate(qc, ["invoices"]); toast.success("Draft deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}
export function usePostInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.invoices.post(id),
    onSuccess: () => { invalidate(qc, ["invoices", "journal"]); toast.success("Invoice posted to the ledger."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to post invoice."),
  });
}
export function usePayInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.invoices.pay(id, data),
    onSuccess: () => { invalidate(qc, ["invoices", "journal"]); toast.success("Payment recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record payment."),
  });
}
export function useVoidInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.invoices.void(id),
    onSuccess: () => { invalidate(qc, ["invoices", "journal"]); toast.success("Invoice voided (reversed)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}

// ── Payroll ─────────────────────────────────────────────────────────────────────

export function usePayrollRuns(params?: { status?: string }) {
  return useQuery<Paginated<PayrollRun>>({ queryKey: ["payroll", params], queryFn: () => financeApi.payroll.list(params) });
}
export function useCreatePayroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.payroll.create(data),
    onSuccess: () => { invalidate(qc, ["payroll"]); toast.success("Payroll run drafted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to draft run."),
  });
}
export function useApprovePayroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payroll.approve(id),
    onSuccess: () => { invalidate(qc, ["payroll", "journal"]); toast.success("Payroll approved + posted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve payroll."),
  });
}
export function useVoidPayroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payroll.void(id),
    onSuccess: () => { invalidate(qc, ["payroll", "journal"]); toast.success("Payroll voided (reversed)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}
export function useDeletePayroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payroll.remove(id),
    onSuccess: () => { invalidate(qc, ["payroll"]); toast.success("Draft deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Salary Advances ───────────────────────────────────────────────────────────

export function useSalaryAdvances(params?: { status?: string; staff_user_id?: string }) {
  return useQuery<SalaryAdvance[]>({ queryKey: ["salary-advances", params], queryFn: () => financeApi.salaryAdvances.list(params) });
}
export function useCreateSalaryAdvance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.salaryAdvances.create(data),
    onSuccess: () => { invalidate(qc, ["salary-advances"]); toast.success("Advance requested."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to request advance."),
  });
}
export function useApproveSalaryAdvance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => financeApi.salaryAdvances.approve(id, data),
    onSuccess: () => { invalidate(qc, ["salary-advances", "journal", "statements"]); toast.success("Advance approved + disbursed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve advance."),
  });
}
export function useRejectSalaryAdvance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.salaryAdvances.reject(id),
    onSuccess: () => { invalidate(qc, ["salary-advances"]); toast.success("Advance rejected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to reject."),
  });
}
export function useRepaySalaryAdvance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.salaryAdvances.repay(id, data),
    onSuccess: () => { invalidate(qc, ["salary-advances", "journal", "statements"]); toast.success("Repayment recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record repayment."),
  });
}
export function useDeleteSalaryAdvance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.salaryAdvances.remove(id),
    onSuccess: () => { invalidate(qc, ["salary-advances"]); toast.success("Request deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Bonus / Reduction Packs (pay adjustments) ─────────────────────────────────

export function usePayAdjustments(params?: { kind?: string; status?: string }) {
  return useQuery<PayAdjustmentPack[]>({ queryKey: ["pay-adjustments", params], queryFn: () => financeApi.payAdjustments.list(params) });
}
export function useCreatePayAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.payAdjustments.create(data),
    onSuccess: () => { invalidate(qc, ["pay-adjustments"]); toast.success("Pack created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create pack."),
  });
}
export function useApprovePayAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payAdjustments.approve(id),
    onSuccess: () => { invalidate(qc, ["pay-adjustments", "journal", "statements"]); toast.success("Pack approved + posted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve pack."),
  });
}
export function useVoidPayAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payAdjustments.void(id),
    onSuccess: () => { invalidate(qc, ["pay-adjustments", "journal", "statements"]); toast.success("Pack voided."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void pack."),
  });
}
export function useDeletePayAdjustment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.payAdjustments.remove(id),
    onSuccess: () => { invalidate(qc, ["pay-adjustments"]); toast.success("Draft deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Requisitions / Request Form ───────────────────────────────────────────────

export function useRequisitions(params?: { status?: string; department?: string }) {
  return useQuery<Requisition[]>({ queryKey: ["requisitions", params], queryFn: () => financeApi.requisitions.list(params) });
}
export function useCreateRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.requisitions.create(data),
    onSuccess: () => { invalidate(qc, ["requisitions"]); toast.success("Requisition submitted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit requisition."),
  });
}
export function useApproveRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.requisitions.approve(id),
    onSuccess: () => { invalidate(qc, ["requisitions", "journal", "statements"]); toast.success("Requisition approved + posted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve requisition."),
  });
}
export function useRejectRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.requisitions.reject(id),
    onSuccess: () => { invalidate(qc, ["requisitions"]); toast.success("Requisition rejected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to reject."),
  });
}
export function useVoidRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.requisitions.void(id),
    onSuccess: () => { invalidate(qc, ["requisitions", "journal", "statements"]); toast.success("Requisition voided."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}
export function useDeleteRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.requisitions.remove(id),
    onSuccess: () => { invalidate(qc, ["requisitions"]); toast.success("Requisition deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Finance Reports ───────────────────────────────────────────────────────────

export function useIncomeExpenseReport(params?: { start?: string; end?: string }) {
  return useQuery<IncomeExpenseReport>({
    queryKey: ["income-expense-report", params],
    queryFn: () => financeApi.reports.incomeExpense(params),
  });
}

// ── Fee Discounts (Manage Discounts) ──────────────────────────────────────────

export function useDiscounts(params?: { status?: string; student_id?: string }) {
  return useQuery<FeeDiscount[]>({ queryKey: ["discounts", params], queryFn: () => financeApi.discounts.list(params) });
}
export function useCreateDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.discounts.create(data),
    onSuccess: () => { invalidate(qc, ["discounts"]); toast.success("Discount proposed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to propose discount."),
  });
}
export function useApproveDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.discounts.approve(id),
    onSuccess: () => { invalidate(qc, ["discounts", "journal", "statements", "fees"]); toast.success("Discount approved + applied."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to approve discount."),
  });
}
export function useRejectDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.discounts.reject(id),
    onSuccess: () => { invalidate(qc, ["discounts"]); toast.success("Discount rejected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to reject."),
  });
}
export function useVoidDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.discounts.void(id),
    onSuccess: () => { invalidate(qc, ["discounts", "journal", "statements", "fees"]); toast.success("Discount voided."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}
export function useDeleteDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.discounts.remove(id),
    onSuccess: () => { invalidate(qc, ["discounts"]); toast.success("Discount deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Fee Assignment (StudentFeeRecord) ─────────────────────────────────────────

export function useFeeRecords(params?: { student_id?: string; term?: string; session_year?: string }) {
  return useQuery<FeeRecord[]>({ queryKey: ["fee-records", params], queryFn: () => financeApi.feeRecords.list(params) });
}
export function useCreateFeeRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.feeRecords.create(data),
    onSuccess: () => { invalidate(qc, ["fee-records", "fees"]); toast.success("Fees assigned."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to assign fees."),
  });
}
export function useUpdateFeeRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.feeRecords.update(id, data),
    onSuccess: () => { invalidate(qc, ["fee-records", "fees"]); toast.success("Fees updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update fees."),
  });
}
export function useDeleteFeeRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.feeRecords.remove(id),
    onSuccess: () => { invalidate(qc, ["fee-records", "fees"]); toast.success("Fee record deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}
export function useAssignClassFees() {
  const qc = useQueryClient();
  return useMutation<ClassFeeAssignResult, any, object>({
    mutationFn: (data: object) => financeApi.feeRecords.assignClass(data),
    onSuccess: (res) => { invalidate(qc, ["fee-records", "fees"]); toast.success(`Assigned to ${res.created} student(s)${res.skipped ? `, ${res.skipped} skipped` : ""}.`); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to assign class fees."),
  });
}
export function useFinanceClasses() {
  return useQuery<ClassOption[]>({ queryKey: ["finance-classes"], queryFn: () => financeApi.classes.list() });
}

// ── Bank Accounts (Account Numbers) ───────────────────────────────────────────

export function useBankAccounts() {
  return useQuery<BankAccount[]>({ queryKey: ["bank-accounts"], queryFn: () => financeApi.bankAccounts.list() });
}
// The primary 'pay to' account — readable by fee-payers (payments:read).
export function usePrimaryBankAccount() {
  return useQuery<BankAccountPublic | null>({ queryKey: ["bank-account-primary"], queryFn: () => financeApi.bankAccounts.primary() });
}

// ── Payment Gateways (org_admin only; secrets encrypted at rest) ──────────────

export function usePaymentGateways() {
  return useQuery<PaymentGateway[]>({ queryKey: ["payment-gateways"], queryFn: () => financeApi.gateways.list() });
}
export function useCreatePaymentGateway() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.gateways.create(data),
    onSuccess: () => { invalidate(qc, ["payment-gateways"]); toast.success("Gateway saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save gateway."),
  });
}
export function useUpdatePaymentGateway() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.gateways.update(id, data),
    onSuccess: () => { invalidate(qc, ["payment-gateways"]); toast.success("Gateway updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeletePaymentGateway() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.gateways.remove(id),
    onSuccess: () => { invalidate(qc, ["payment-gateways"]); toast.success("Gateway removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Accounts Setup (default posting accounts) ─────────────────────────────────

export function useFinanceSettings() {
  return useQuery<FinanceSettings>({ queryKey: ["finance-settings"], queryFn: () => financeApi.settings.get() });
}
export function useUpdateFinanceSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.settings.update(data),
    onSuccess: () => { invalidate(qc, ["finance-settings"]); toast.success("Default accounts saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save."),
  });
}
export function useCreateBankAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.bankAccounts.create(data),
    onSuccess: () => { invalidate(qc, ["bank-accounts"]); toast.success("Bank account added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add account."),
  });
}
export function useUpdateBankAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.bankAccounts.update(id, data),
    onSuccess: () => { invalidate(qc, ["bank-accounts"]); toast.success("Account updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useSetPrimaryBankAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.bankAccounts.setPrimary(id),
    onSuccess: () => { invalidate(qc, ["bank-accounts"]); toast.success("Primary account set."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to set primary."),
  });
}
export function useDeleteBankAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.bankAccounts.remove(id),
    onSuccess: () => { invalidate(qc, ["bank-accounts"]); toast.success("Account removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Budgets ─────────────────────────────────────────────────────────────────────

export function useBudgets() {
  return useQuery<Budget[]>({ queryKey: ["budgets"], queryFn: () => financeApi.budgets.list() });
}
export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.budgets.create(data),
    onSuccess: () => { invalidate(qc, ["budgets"]); toast.success("Budget set."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to set budget."),
  });
}
export function useUpdateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.budgets.update(id, data),
    onSuccess: () => { invalidate(qc, ["budgets"]); toast.success("Budget updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update budget."),
  });
}
export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.budgets.remove(id),
    onSuccess: () => { invalidate(qc, ["budgets"]); toast.success("Budget removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Petty Cash ──────────────────────────────────────────────────────────────────

export function usePettyCash() {
  return useQuery<Paginated<PettyCashTxn>>({ queryKey: ["petty-cash"], queryFn: () => financeApi.pettyCash.list() });
}
export function useRecordPettyCash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.pettyCash.create(data),
    onSuccess: (txn: PettyCashTxn) => {
      invalidate(qc, ["petty-cash", "budgets", "journal"]);
      if (txn?.warning) toast.warning(txn.warning); else toast.success("Petty cash recorded.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function useVoidPettyCash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.pettyCash.void(id),
    onSuccess: () => { invalidate(qc, ["petty-cash", "journal"]); toast.success("Voided (reversed)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}

// ── Cash Transactions ─────────────────────────────────────────────────────────

export function useCashTxns(params?: { type?: string }) {
  return useQuery<Paginated<CashTransaction>>({ queryKey: ["cash", params], queryFn: () => financeApi.cash.list(params) });
}
export function useRecordCash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.cash.create(data),
    onSuccess: () => { invalidate(qc, ["cash", "journal"]); toast.success("Transaction recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function useVoidCash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.cash.void(id),
    onSuccess: () => { invalidate(qc, ["cash", "journal"]); toast.success("Voided (reversed)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}

// ── Store & Inventory ─────────────────────────────────────────────────────────

export function useStoreItems() {
  return useQuery<Paginated<StoreItem>>({ queryKey: ["store-items"], queryFn: () => financeApi.store.items() });
}
export function useCreateStoreItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.store.createItem(data),
    onSuccess: () => { invalidate(qc, ["store-items"]); toast.success("Item added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add item."),
  });
}
export function useUpdateStoreItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.store.updateItem(id, data),
    onSuccess: () => { invalidate(qc, ["store-items"]); toast.success("Item updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteStoreItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.store.removeItem(id),
    onSuccess: () => { invalidate(qc, ["store-items"]); toast.success("Item removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function usePurchaseStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.store.purchase(id, data),
    onSuccess: () => { invalidate(qc, ["store-items", "journal"]); toast.success("Stock purchased + posted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to purchase."),
  });
}
export function useAdjustStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.store.adjust(id, data),
    onSuccess: () => { invalidate(qc, ["store-items"]); toast.success("Stock updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update stock."),
  });
}

// ── Store Front Desk (POS sales) ──────────────────────────────────────────────

export function useStoreSales(params?: { status?: string }) {
  return useQuery<StoreSale[]>({ queryKey: ["store-sales", params], queryFn: () => financeApi.store.sales(params) });
}
export function useCreateStoreSale() {
  const qc = useQueryClient();
  return useMutation<StoreSale, any, object>({
    mutationFn: (data: object) => financeApi.store.createSale(data),
    onSuccess: () => { invalidate(qc, ["store-sales", "store-items", "journal", "statements"]); toast.success("Sale recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record sale."),
  });
}
export function useVoidStoreSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.store.voidSale(id),
    onSuccess: () => { invalidate(qc, ["store-sales", "store-items", "journal", "statements"]); toast.success("Sale voided."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to void."),
  });
}
export function useStoreSalesSummary(params?: { start?: string; end?: string }) {
  return useQuery<StoreSalesSummary>({ queryKey: ["store-sales-summary", params], queryFn: () => financeApi.store.salesSummary(params) });
}

// ── Warehouse (multi-location stock) ──────────────────────────────────────────

export function useWarehouses() {
  return useQuery<Warehouse[]>({ queryKey: ["warehouses"], queryFn: () => financeApi.warehouse.list() });
}
export function useWarehouseStock(id: string | null) {
  return useQuery<WarehouseStockRow[]>({ queryKey: ["warehouse-stock", id], queryFn: () => financeApi.warehouse.stock(id as string), enabled: !!id });
}
export function useCreateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.warehouse.create(data),
    onSuccess: () => { invalidate(qc, ["warehouses"]); toast.success("Warehouse added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add warehouse."),
  });
}
export function useUpdateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.warehouse.update(id, data),
    onSuccess: () => { invalidate(qc, ["warehouses"]); toast.success("Warehouse updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.warehouse.remove(id),
    onSuccess: () => { invalidate(qc, ["warehouses", "warehouse-stock"]); toast.success("Warehouse removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function useReceiveStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.warehouse.receive(data),
    onSuccess: () => { invalidate(qc, ["warehouses", "warehouse-stock"]); toast.success("Stock received."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to receive stock."),
  });
}
export function useTransferStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.warehouse.transfer(data),
    onSuccess: () => { invalidate(qc, ["warehouses", "warehouse-stock"]); toast.success("Stock transferred."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to transfer."),
  });
}
export function useIssueStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.warehouse.issue(data),
    onSuccess: () => { invalidate(qc, ["warehouses", "warehouse-stock"]); toast.success("Stock issued out."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to issue."),
  });
}

// ── Store Pickup Unit ─────────────────────────────────────────────────────────

export function usePickupPoints() {
  return useQuery<PickupPoint[]>({ queryKey: ["pickup-points"], queryFn: () => financeApi.pickup.points() });
}
export function usePickups(params?: { status?: string; pickup_point_id?: string }) {
  return useQuery<Pickup[]>({ queryKey: ["pickups", params], queryFn: () => financeApi.pickup.list(params) });
}
export function useCreatePickupPoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.pickup.createPoint(data),
    onSuccess: () => { invalidate(qc, ["pickup-points"]); toast.success("Pickup point added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add pickup point."),
  });
}
export function useUpdatePickupPoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => financeApi.pickup.updatePoint(id, data),
    onSuccess: () => { invalidate(qc, ["pickup-points"]); toast.success("Pickup point updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeletePickupPoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.pickup.removePoint(id),
    onSuccess: () => { invalidate(qc, ["pickup-points"]); toast.success("Pickup point removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function useCreatePickup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => financeApi.pickup.create(data),
    onSuccess: () => { invalidate(qc, ["pickups", "pickup-points"]); toast.success("Pickup ticket created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create pickup."),
  });
}
export function useCollectPickup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.pickup.collect(id),
    onSuccess: () => { invalidate(qc, ["pickups", "pickup-points"]); toast.success("Marked as collected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to mark collected."),
  });
}
export function useCancelPickup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.pickup.cancel(id),
    onSuccess: () => { invalidate(qc, ["pickups", "pickup-points"]); toast.success("Pickup cancelled."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to cancel."),
  });
}
export function useDeletePickup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => financeApi.pickup.remove(id),
    onSuccess: () => { invalidate(qc, ["pickups", "pickup-points"]); toast.success("Pickup deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}
