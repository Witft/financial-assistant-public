import { test, expect } from '@playwright/test'
import { attachConsoleGuard } from './helpers/consoleGuard'

test('error banner is cleared when a subsequent correction succeeds', async ({ page }) => {
  const errors = attachConsoleGuard(page, {
    ignoredMessages: [
      'Failed to load resource: the server responded with a status of 500 (Internal Server Error)',
      'Failed to persist transaction category: Error: 保存失败，请稍后重试',
    ],
  })
  const correctionRequests: Array<Record<string, unknown>> = []

  const months = ['2026-05']
  const summary = {
    success: true,
    month: '2026-05',
    summary: {
      income: 10000,
      expense: 100,
      transfer: 0,
      balance: 9900,
      transaction_count: 2,
    },
    category_expenses: [],
  }

  const transactions = [
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
      amount: -100,
      category: 'other',
      description: '麦当劳',
      source: 'alipay',
      type: 'expense',
      confidence: 0.42,
      requires_human_review: true,
    },
  ]

  let correctionAttempt = 0

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
    correctionAttempt++
    const body = route.request().postDataJSON() as Record<string, unknown>
    correctionRequests.push(body)

    if (correctionAttempt === 1) {

      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '保存失败，请稍后重试' }),
      })
    } else {

      transactions[0] = {
        ...transactions[0],
        category: 'income',
        confidence: 1.0,
        requires_human_review: false,
      }

      await route.fulfill({
        json: {
          success: true,
          message: 'correction saved',
        },
      })
    }
  })

  await page.goto('/review')

  await expect(page.getByTestId('review-row-tx_salary')).toBeVisible()
  await expect(page.getByTestId('review-row-tx_mcd')).toBeVisible()

  // First correction fails → error banner appears
  await page.getByTestId('review-category-tx_salary').selectOption('收入')

  await expect.poll(() => correctionRequests.length).toBe(1)
  await expect(page.getByTestId('review-row-tx_salary')).toBeVisible()
  await expect(page.getByTestId('review-category-tx_salary')).toHaveValue('其他')
  await expect(page.getByTestId('review-error-banner')).toBeVisible()
  await expect(page.getByTestId('review-error-banner')).toContainText('保存失败，请稍后重试')

  // Second correction succeeds → error banner cleared, transaction gone
  await page.getByTestId('review-category-tx_salary').selectOption('收入')

  await expect.poll(() => correctionRequests.length).toBe(2)
  await expect(page.getByTestId('review-row-tx_salary')).toHaveCount(0)
  await expect(page.getByTestId('review-error-banner')).toHaveCount(0)
  await expect(page.getByTestId('review-row-tx_mcd')).toBeVisible()

  expect(correctionRequests[1]).toMatchObject({
    transaction_id: 'tx_salary',
    description: '工资',
    category: 'income',
  })
  expect(errors).toEqual([])
})
