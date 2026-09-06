import { test, expect } from '@playwright/test'
import { attachConsoleGuard } from './helpers/consoleGuard'

test('dashboard renders latest import job card and can jump to review flow', async ({ page }) => {
  const errors = attachConsoleGuard(page)

  const months = ['2026-05']
  const latestImportJob = {
    id: 'job_review_1',
    status: 'REVIEW_REQUIRED',
    source: 'alipay',
    filename: 'alipay-may.csv',
    total_transactions: 2,
    review_required_count: 1,
    persisted_count: 2,
    error_message: null,
    created_at: '2026-05-19T03:00:00Z',
    started_at: '2026-05-19T03:00:01Z',
    finished_at: '2026-05-19T03:00:02Z',
    updated_at: '2026-05-19T03:00:03Z',
  }

  const summary = {
    success: true,
    month: '2026-05',
    summary: {
      income: 0,
      expense: 35,
      transfer: 0,
      balance: -35,
      transaction_count: 2,
    },
    category_expenses: [{ category: 'dining', amount: 35, transaction_count: 1 }],
  }

  const transactions = [
    {
      id: 'tx_pending_1',
      date: '2026-05-19',
      amount: -20,
      category: 'other',
      description: '未知商户A',
      source: 'alipay',
      type: 'expense',
      confidence: 0.15,
      requires_human_review: true,
      import_job_id: 'job_review_1',
    },
    {
      id: 'tx_done_1',
      date: '2026-05-18',
      amount: -15,
      category: 'dining',
      description: '兰州拉面',
      source: 'alipay',
      type: 'expense',
      confidence: 0.95,
      requires_human_review: false,
      import_job_id: 'job_review_1',
    },
  ]

  await page.route('**/api/agent/months', async route => {
    await route.fulfill({ json: { success: true, months } })
  })

  await page.route('**/api/import-jobs/latest', async route => {
    await route.fulfill({ json: { success: true, job: latestImportJob } })
  })

  await page.route('**/api/agent/monthly-summary?**', async route => {
    await route.fulfill({ json: summary })
  })

  await page.route('**/api/agent/transactions?**', async route => {
    await route.fulfill({
      json: {
        success: true,
        transactions,
      },
    })
  })

  await page.goto('/dashboard')

  await expect(page.getByTestId('latest-import-job-card')).toBeVisible()
  await expect(page.getByText('alipay-may.csv')).toBeVisible()
  await expect(page.getByTestId('latest-import-job-status')).toHaveText('待审核')
  await expect(page.getByText('来源：支付宝')).toBeVisible()
  await expect(page.getByText('总笔数：2')).toBeVisible()
  await expect(page.getByText('已入库：2')).toBeVisible()
  await expect(page.getByText('待审核：1')).toBeVisible()
  await expect(page.getByText('更新时间：')).toBeVisible()

  await page.getByRole('link', { name: '去处理待审核交易 →' }).click()

  await expect(page).toHaveURL(/\/review/)
  await expect(page.getByTestId('review-row-tx_pending_1')).toBeVisible()
  await expect(page.getByTestId('review-category-tx_pending_1')).toHaveValue('其他')

  expect(errors).toEqual([])
})
