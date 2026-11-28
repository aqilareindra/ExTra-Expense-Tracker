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
