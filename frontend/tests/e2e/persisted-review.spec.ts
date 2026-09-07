import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { attachConsoleGuard } from './helpers/consoleGuard'

const apiBase = process.env.FINANCIAL_REAL_API_BASE_URL
const enabled = process.env.FINANCIAL_REAL_DB_E2E === '1' && Boolean(apiBase)
const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = path.resolve(here, '../../../backend/tests/fixtures/ccb_sample.xls')

test.describe('real persisted review correction', () => {
  test.skip(!enabled, 'requires FINANCIAL_REAL_DB_E2E=1 and FINANCIAL_REAL_API_BASE_URL; this spec never mocks API calls')

  test('CCB upload corrects the exact parsed persisted ID and remains corrected after reload', async ({ page, request }) => {
    const errors = attachConsoleGuard(page)
    const navigationDiagnosticPath = process.env.FINANCIAL_REAL_NAV_DIAGNOSTIC_PATH
    const navigationEvents: Array<{ event: string, url: string, detail: string }> = []
    const recordNavigationEvent = (event: string, url: string, detail = '') => {
      if (navigationEvents.length < 250) {
        navigationEvents.push({ event, url, detail })
      }
      if (navigationDiagnosticPath) {
        writeFileSync(navigationDiagnosticPath, JSON.stringify({ navigationEvents }, null, 2))
      }
    }
    page.on('request', request => recordNavigationEvent('request', request.url(), `${request.method()} ${request.resourceType()}`))
    page.on('requestfailed', request => recordNavigationEvent('requestfailed', request.url(), request.failure()?.errorText || 'unknown failure'))
    page.on('response', response => recordNavigationEvent('response', response.url(), `${response.status()} ${response.request().resourceType()}`))
    page.on('response', response => {
      if (response.status() >= 400) {
        errors.push(`http: ${response.status()} ${new URL(response.url()).pathname}`)
      }
    })

    // `load` waits for every subresource; the workflow only requires a mounted
    // upload control. The native file input is intentionally CSS-hidden, so the
    // visible drop zone plus attached input are the explicit readiness boundary.
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.drop-zone')).toBeVisible()
    await expect(page.locator('input[type="file"]')).toBeAttached()
    if (navigationDiagnosticPath) {
      await page.screenshot({ path: `${navigationDiagnosticPath}.png` })
    }
    const parsedResponsePromise = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/parse' && response.request().method() === 'POST'
    )
    await page.locator('input[type="file"]').setInputFiles(fixture)

    const parsedResponse = await parsedResponsePromise
    expect(parsedResponse.status()).toBe(200)
    const parsed = await parsedResponse.json()
    expect(parsed).toMatchObject({ success: true, persisted_count: 12, job_status: 'REVIEW_REQUIRED' })
    expect(parsed.transactions).toHaveLength(12)
    expect(parsed.job_id).toMatch(/^job_/)

    const month = String(parsed.transactions[0]?.date || '').slice(0, 7)
    expect(month).toMatch(/^\d{4}-\d{2}$/)
    const rowsResponse = await request.get(`${apiBase}/agent/transactions?month=${month}&limit=50`)
    expect(rowsResponse.status()).toBe(200)
    const uploadedRows = await rowsResponse.json()
    expect(uploadedRows.transactions).toHaveLength(12)

    const target = uploadedRows.transactions.find((row: any) =>
      row.requires_human_review === true && parsed.transactions.some((tx: any) => tx.id === row.id)
    )
    expect(target).toBeTruthy()
    const parsedTarget = parsed.transactions.find((tx: any) => tx.id === target.id)
    expect(parsedTarget).toMatchObject({ id: target.id, description: target.description })
    expect(target.import_job_id).toBe(parsed.job_id)

    await expect(page).toHaveURL(/\/review/, { timeout: 15_000 })
    await expect(page.getByTestId(`review-row-${target.id}`)).toBeVisible()

    const correctionResponsePromise = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/transactions/correct' && response.request().method() === 'POST'
    )
    await page.getByTestId(`review-category-${target.id}`).selectOption('餐饮')

    const correctionResponse = await correctionResponsePromise
    expect(correctionResponse.status()).toBe(200)
    const correction = await correctionResponse.json()
    expect(correction).toMatchObject({ success: true, normalized_category: 'dining', updated_transaction: true })
    expect(correctionResponse.request().postDataJSON()).toEqual(expect.objectContaining({
      transaction_id: target.id,
      description: target.description,
      category: 'dining',
      job_id: parsed.job_id,
    }))

    await expect(page.getByTestId(`review-row-${target.id}`)).toHaveCount(0)
    await expect(page.getByTestId('review-error-banner')).toHaveCount(0)

    const correctedRowsResponse = await request.get(`${apiBase}/agent/transactions?month=${month}&limit=50`)
    expect(correctedRowsResponse.status()).toBe(200)
    const correctedRows = await correctedRowsResponse.json()
    const persisted = correctedRows.transactions.find((row: any) => row.id === target.id)
    expect(persisted).toMatchObject({
      id: target.id,
      category: 'dining',
      requires_human_review: false,
      import_job_id: parsed.job_id,
    })

    const statePath = process.env.FINANCIAL_REAL_STATE_PATH
    expect(statePath, 'runner must collect exact identity for independent SQL proof').toBeTruthy()
    mkdirSync(path.dirname(statePath!), { recursive: true })
    writeFileSync(statePath!, JSON.stringify({
      target_id: target.id,
      target_description: target.description,
      job_id: parsed.job_id,
      month,
      uploaded_count: uploadedRows.transactions.length,
      selected_category: 'dining',
    }, null, 2))

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('review-page')).toBeVisible()
    await expect(page.getByTestId(`review-row-${target.id}`)).toHaveCount(0)
    await expect(page.getByTestId('review-error-banner')).toHaveCount(0)
    expect(errors).toEqual([])
  })
})
