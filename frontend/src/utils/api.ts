import type { AiDiagnosisResult, ImportJob, MonthlySummaryPayload, Transaction } from '@/types/finance'
import { normalizeCategoryCode, normalizeCategoryLabel } from '@/utils/category'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function getErrorMessage(data: any, fallback: string) {
  return data?.detail || data?.message || fallback
}

function normalizeImportJob(job: any): ImportJob {
  return {
    id: job.id,
    status: job.status,
    source: job.source,
    filename: job.filename,
    total_transactions: Number(job.total_transactions || 0),
    review_required_count: Number(job.review_required_count || 0),
    persisted_count: Number(job.persisted_count || 0),
    error_message: job.error_message || null,
    created_at: job.created_at || null,
    started_at: job.started_at || null,
    finished_at: job.finished_at || null,
    updated_at: job.updated_at || null,
  }
}

async function parseJsonResponse(response: Response, fallbackMessage: string) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(getErrorMessage(data, `${fallbackMessage}: ${response.status} ${response.statusText}`))
  }

  return data
}

function normalizeTransaction(tx: any): Transaction {
  return {
    id: tx.id,
    date: tx.date,
    amount: tx.amount,
    category: normalizeCategoryLabel(tx.category),
    description: tx.description,
    source: tx.source,
    type: tx.type,
    confidence: tx.confidence,
    requires_human_review: tx.requires_human_review,
    import_job_id: tx.import_job_id,
  }
}

export async function fetchAiDiagnosis(promptData: any): Promise<AiDiagnosisResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        financial_data: promptData,
      }),
    })

    const data = (await parseJsonResponse(response, 'AI 分析请求失败')) as AiDiagnosisResult
    return data
  } catch (error) {
    console.error('AI 分析接口调用失败:', error)
    throw error
  }
}

export async function fetchParsedTransactions(file: File) {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE_URL}/parse`, {
      method: 'POST',
      body: formData,
    })

    const data = await parseJsonResponse(response, '文件解析失败')

    if (data.success && Array.isArray(data.transactions)) {
      return {
        transactions: data.transactions.map(normalizeTransaction),
        message: data.message || '',
      }
    }

    throw new Error(data.message || '解析返回格式错误')
  } catch (error) {
    console.error('文件解析 API 调用失败:', error)
    throw error
  }
}

export async function fetchAgentMonths(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/agent/months`)
  const data = await parseJsonResponse(response, '读取月份列表失败')

  if (data.success && Array.isArray(data.months)) {
    return data.months
  }

  throw new Error(getErrorMessage(data, '月份列表返回格式错误'))
}

export async function fetchLatestImportJob(): Promise<ImportJob | null> {
  const response = await fetch(`${API_BASE_URL}/import-jobs/latest`)
  const data = await parseJsonResponse(response, '读取最近导入任务失败')

  if (data.success) {
    return data.job ? normalizeImportJob(data.job) : null
  }

  throw new Error(getErrorMessage(data, '最近导入任务返回格式错误'))
}

export async function fetchMonthlySummary(month: string): Promise<MonthlySummaryPayload> {
  const params = new URLSearchParams({ month })
  const response = await fetch(`${API_BASE_URL}/agent/monthly-summary?${params.toString()}`)
  const data = await parseJsonResponse(response, '读取月度汇总失败')

  if (data.success && data.summary) {
    return {
      month: data.month,
      summary: {
        income: Number(data.summary.income || 0),
        expense: Number(data.summary.expense || 0),
        transfer: Number(data.summary.transfer || 0),
        balance: Number(data.summary.balance || 0),
        transaction_count: Number(data.summary.transaction_count || 0),
      },
      category_expenses: Array.isArray(data.category_expenses)
        ? data.category_expenses.map((item: any) => ({
            category: normalizeCategoryLabel(item.category),
            amount: Number(item.amount || 0),
            transaction_count: Number(item.transaction_count || 0),
          }))
        : [],
    }
  }

  throw new Error(getErrorMessage(data, '月度汇总返回格式错误'))
}

export async function fetchAgentTransactions(month: string, limit = 200): Promise<Transaction[]> {
  const params = new URLSearchParams({
    month,
    limit: String(limit),
  })

  const response = await fetch(`${API_BASE_URL}/agent/transactions?${params.toString()}`)
  const data = await parseJsonResponse(response, '读取交易明细失败')

  if (data.success && Array.isArray(data.transactions)) {
    return data.transactions.map(normalizeTransaction)
  }

  throw new Error(getErrorMessage(data, '交易明细返回格式错误'))
}

export async function submitTransactionCorrection({
  transactionId,
  description,
  category,
  jobId,
}: {
  transactionId: string
  description?: string
  category: string
  jobId?: string
}) {
  const response = await fetch(`${API_BASE_URL}/transactions/correct`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      transaction_id: transactionId,
      description,
      category: normalizeCategoryCode(category),
      job_id: jobId,
    }),
  })

  return parseJsonResponse(response, '保存交易分类失败')
}
