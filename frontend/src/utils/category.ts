const CATEGORY_MAPPING: Record<string, string> = {
  family_support: '转账',
  investment: '投资理财',
  dining: '餐饮',
  transportation: '交通',
  fitness_health: '健身健康',
  housing: '住房',
  personal_care: '个人护理',
  education: '教育',
  healthcare: '医疗',
  shopping: '购物',
  entertainment: '娱乐',
  digital_subscription: '数码订阅',
  daily_necessities: '日用百货',
  income: '收入',
  other: '其他',
}

const CATEGORY_CODE_MAPPING: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_MAPPING).map(([code, label]) => [label, code])
)

/**
 * Normalize category values from different API/cache generations into a UI-safe label.
 *
 * Historical /api/categorize responses returned objects like:
 * { category: '餐饮', confidence: 0.85, reason: '...' }
 * If such an object leaks into Vue templates it renders as "[object Object]".
 */
export function normalizeCategoryLabel(value: unknown): string {
  if (typeof value === 'string') {
    return CATEGORY_MAPPING[value] || value
  }

  if (value && typeof value === 'object' && 'category' in value) {
    const nestedCategory = (value as { category?: unknown }).category
    return normalizeCategoryLabel(nestedCategory)
  }

  return '其他'
}

export function normalizeCategoryCode(value: unknown): string {
  if (typeof value === 'string') {
    return CATEGORY_CODE_MAPPING[value] || value
  }

  if (value && typeof value === 'object' && 'category' in value) {
    const nestedCategory = (value as { category?: unknown }).category
    return normalizeCategoryCode(nestedCategory)
  }

  return 'other'
}

export function normalizeCategoryMapping(mapping: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(mapping).map(([description, category]) => [
      description,
      normalizeCategoryLabel(category),
    ])
  )
}
