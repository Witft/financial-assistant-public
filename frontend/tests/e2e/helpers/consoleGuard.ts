import type { Page } from '@playwright/test'

interface ConsoleGuardOptions {
  ignoredMessages?: Array<string | RegExp>
}

function shouldIgnoreMessage(message: string, ignoredMessages: Array<string | RegExp>) {
  return ignoredMessages.some(pattern =>
    typeof pattern === 'string' ? message.includes(pattern) : pattern.test(message)
  )
}

export function attachConsoleGuard(page: Page, options: ConsoleGuardOptions = {}) {
  const errors: string[] = []
  const ignoredMessages = options.ignoredMessages || []

  page.on('pageerror', error => {
    const message = `pageerror: ${error.message}`
    if (!shouldIgnoreMessage(message, ignoredMessages)) {
      errors.push(message)
    }
  })

  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('favicon')) {
      const message = `console: ${msg.text()}`
      if (!shouldIgnoreMessage(message, ignoredMessages)) {
        errors.push(message)
      }
    }
  })

  return errors
}
