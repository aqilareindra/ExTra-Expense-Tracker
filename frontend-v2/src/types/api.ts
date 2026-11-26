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

export interface EditableItemDraft {
  localId: string;
  name: string;
  category: ExpenseCategory;
  price: string;
  nameError?: string;
  categoryError?: string;
  priceError?: string;
}
