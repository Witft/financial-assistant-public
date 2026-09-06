import { describe, expect, it } from 'vitest'
import {
  normalizeCategoryCode,
  normalizeCategoryLabel,
  normalizeCategoryMapping,
} from '../src/utils/category'

describe('category normalization', () => {
  it('maps backend category codes to UI labels', () => {
    expect(normalizeCategoryLabel('dining')).toBe('餐饮')
    expect(normalizeCategoryLabel('digital_subscription')).toBe('数码订阅')
    expect(normalizeCategoryLabel('income')).toBe('收入')
  })

  it('maps UI labels back to backend category codes', () => {
    expect(normalizeCategoryCode('餐饮')).toBe('dining')
    expect(normalizeCategoryCode('转账')).toBe('family_support')
    expect(normalizeCategoryCode('收入')).toBe('income')
  })

  it('extracts category label from structured AI category result', () => {
    expect(
      normalizeCategoryLabel({
        category: '餐饮',
        confidence: 0.86,
        reason: '包含咖啡关键词',
        requires_human_review: false,
      })
    ).toBe('餐饮')
  })

  it('normalizes a mapping returned by /api/categorize before it reaches UI state', () => {
    expect(
      normalizeCategoryMapping({
        星巴克: { category: '餐饮', confidence: 0.9 },
        Bandwagon: { category: 'digital_subscription', confidence: 0.9 },
      })
    ).toEqual({
      星巴克: '餐饮',
      Bandwagon: '数码订阅',
    })
  })
})
