import type { ExpenseCategory } from "../constants/categories";

export interface ValidationErrorDetail {
  field: string;
  message: string;
}

export interface ApiErrorResponse {
  status: "error";
  error_code: string;
  message: string;
  details?: ValidationErrorDetail[] | null;
}

export interface ExtractedItem {
  name: string;
  price: number;
  category: ExpenseCategory;
}

export interface ReceiptPreviewData {
  date: string | null;
  items: ExtractedItem[];
}

export interface ReceiptExtractResponse {
  status: "success";
  data: ReceiptPreviewData;
  warnings: string[];
  temp_image_token: string | null;
}

export interface TransactionItemCreate {
  name: string;
  price: number;
  category: ExpenseCategory;
}

export interface TransactionCreateRequest {
  date: string;
  items: TransactionItemCreate[];
  temp_image_token?: string | null;
}

export interface TransactionItemRecord {
  id: number;
  transaction_id: number;
  date: string;
  name: string;
  category: ExpenseCategory;
  price: number;
  has_receipt: boolean;
  created_at: string;
}

export interface TransactionCreatedData {
  transaction_id: number;
  date: string;
  has_receipt: boolean;
  created_at: string;
  items: TransactionItemRecord[];
}

export interface TransactionCreateResponse {
  status: "success";
  data: TransactionCreatedData;
}

export interface TransactionListFilters {
  month?: number | "";
  year?: number | "";
  category?: ExpenseCategory | "";
  search?: string;
}

export interface TransactionListResponse {
  status: "success";
  count: number;
  data: TransactionItemRecord[];
}

export interface ItemUpdateRequest {
  name?: string;
  price?: number;
  date?: string;
  category?: ExpenseCategory;
}

export interface ItemUpdateResponse {
  status: "success";
  data: TransactionItemRecord;
}

export interface ItemDeleteResponse {
  status: "success";
  message: string;
  deleted_item_id: number;
  orphan_transaction_deleted: boolean;
}

export interface TransactionDeleteResponse {
  status: "success";
  message: string;
  deleted_transaction_id: number;
}

export interface DailyExpenseBreakdown {
  date: string;
  total: number;
  item_count: number;
}

export interface CategoryExpenseBreakdown {
  category: ExpenseCategory;
  total: number;
  item_count: number;
}

export interface MonthlySummaryResponse {
  status: "success";
  month: number;
  year: number;
  total_expense: number;
  total_income: number;
  net_balance: number;
  total_items: number;
  daily_breakdown: DailyExpenseBreakdown[];
  category_breakdown: CategoryExpenseBreakdown[];
}

export interface EditableItemDraft {
  localId: string;
  name: string;
  category: ExpenseCategory;
  price: string;
  nameError?: string;
  categoryError?: string;
  priceError?: string;
}

export interface AuthUser {
  id: number;
  email: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface AuthSuccessResponse {
  status: "success";
  message: string;
  data: AuthUser;
}

export interface CurrentUserResponse {
  status: "success";
  data: AuthUser;
}

export interface LogoutResponse {
  status: "success";
  message: string;
}

export interface IncomeCreateRequest {
  income_date: string;
  source_name: string;
  amount: number;
}

export interface IncomeRecord {
  id: number;
  income_date: string;
  source_name: string;
  amount: number;
  created_at: string;
}

export interface IncomeResponse {
  status: "success";
  data: IncomeRecord;
}

export interface IncomeListResponse {
  status: "success";
  count: number;
  total_income: number;
  data: IncomeRecord[];
}

export interface IncomeDeleteResponse {
  status: "success";
  message: string;
  deleted_income_id: number;
}

export type BudgetStatus = "safe" | "warning" | "over_budget";

export interface BudgetUpsertRequest {
  month: number;
  year: number;
  category: ExpenseCategory;
  limit_amount: number;
}

export interface BudgetStatusItem {
  id: number;
  month: number;
  year: number;
  category: ExpenseCategory;
  limit_amount: number;
  spent_amount: number;
  remaining_amount: number;
  usage_percentage: number;
  status: BudgetStatus;
}

export interface BudgetUpsertResponse {
  status: "success";
  message: string;
  data: BudgetStatusItem;
}

export interface BudgetListResponse {
  status: "success";
  month: number;
  year: number;
  total_budget: number;
  total_spent: number;
  total_remaining: number;
  data: BudgetStatusItem[];
}

export interface BudgetDeleteResponse {
  status: "success";
  message: string;
  deleted_budget_id: number;
}

export interface InsightsTopCategoryItem {
  category: ExpenseCategory;
  total: number;
  share_percentage: number;
  item_count: number;
}

export interface InsightsBudgetAlertItem {
  category: ExpenseCategory;
  limit_amount: number;
  spent_amount: number;
  remaining_amount: number;
  usage_percentage: number;
  status: BudgetStatus;
}

export interface InsightsMetricsSnapshot {
  month: number;
  year: number;
  total_income: number;
  total_expense: number;
  net_balance: number;
  total_items: number;
  previous_month: number;
  previous_year: number;
  previous_month_expense: number;
  mom_expense_change_amount: number;
  mom_expense_change_percentage: number | null;
  top_categories: InsightsTopCategoryItem[];
  budget_alerts: InsightsBudgetAlertItem[];
}

export interface MonthlyInsightsResponse {
  status: "success";
  month: number;
  year: number;
  has_data: boolean;
  summary_text: string;
  recommendations: string[];
  metrics_snapshot: InsightsMetricsSnapshot;
}
