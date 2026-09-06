export type TransactionType = 'expense' | 'income' | 'transfer'
export type SourceType = 'wechat' | 'alipay' | 'ccb' | 'other' | 'unknown'

export interface Transaction {
  id: string
  date: string
  amount: number
  category: string
  description?: string
  source: SourceType
  type: TransactionType
  confidence?: number
  requires_human_review?: boolean
  import_job_id?: string
}

export interface CategoryExpense {
  category: string
  amount: number
  transaction_count: number
}

export interface MonthlySummary {
  income: number
  expense: number
  transfer: number
  balance: number
  transaction_count: number
}

export interface MonthlySummaryPayload {
  month: string
  summary: MonthlySummary
  category_expenses: CategoryExpense[]
}

export interface AiDiagnosisResult {
  success: boolean
  result: string
}

export interface ImportJob {
  id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'REVIEW_REQUIRED' | string
  source: SourceType
  filename: string
  total_transactions: number
  review_required_count: number
  persisted_count: number
  error_message?: string | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string | null
}
