import { test, expect } from '@playwright/test'
import { attachConsoleGuard } from './helpers/consoleGuard'

test('review correction persists across reload and dashboard navigation', async ({ page }) => {
  const errors = attachConsoleGuard(page)
  const correctionRequests: Array<Record<string, unknown>> = []

  const months = ['2026-05']
  const summary = {
    success: true,
    month: '2026-05',
    summary: {
      income: 10000,
      expense: 39,
      transfer: 0,
      balance: 9961,
      transaction_count: 2,
    },
    category_expenses: [
      { category: 'dining', amount: 39, transaction_count: 1 },
    ],
  }

  let transactions = [
    {
      id: 'tx_salary',
      date: '2026-05-02',
      amount: 10000,
      category: 'other',
      description: '工资',
      source: 'wechat',
      type: 'income',
      confidence: 0.42,
      requires_human_review: true,
    },
    {
      id: 'tx_mcd',
      date: '2026-05-01',
      amount: -39,
      category: 'dining',
      description: '麦当劳',
      source: 'alipay',
      type: 'expense',
      confidence: 0.99,
      requires_human_review: false,
    },
  ]

  await page.route('**/api/agent/months', async route => {
    await route.fulfill({ json: { success: true, months } })
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

  await page.route('**/api/transactions/correct', async route => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    correctionRequests.push(body)

    expect(body).toMatchObject({
      transaction_id: 'tx_salary',
      description: '工资',
      category: 'income',
    })

    transactions = transactions.map(tx =>
      tx.id === 'tx_salary'
        ? {
            ...tx,
            category: 'income',
            confidence: 1.0,
            requires_human_review: false,
          }
        : tx
    )

    await route.fulfill({
      json: {
        success: true,
        message: 'correction saved',
      },
    })
  })

  await page.goto('/review')

  await expect(page.getByTestId('review-page')).toBeVisible()
  await expect(page.getByTestId('review-row-tx_salary')).toBeVisible()
  await expect(page.getByTestId('review-category-tx_salary')).toHaveValue('其他')

  await page.getByTestId('review-category-tx_salary').selectOption('收入')

  await expect.poll(() => correctionRequests.length).toBe(1)
  await expect(page.getByTestId('review-row-tx_salary')).toHaveCount(0)
  await expect(page.getByTestId('review-empty-state')).toBeVisible()

  await page.reload()

  await expect(page.getByTestId('review-empty-state')).toBeVisible()
  await expect(page.getByTestId('review-row-tx_salary')).toHaveCount(0)

  await page.getByTestId('review-finish-button').click()
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole('heading', { name: '📊 财务 Dashboard' })).toBeVisible()
  await expect(page.getByText('工资')).toBeVisible()

  expect(errors).toEqual([])
})
