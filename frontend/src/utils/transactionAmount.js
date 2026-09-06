export function formatTransactionAmount(amount, type) {
  const normalized = `¥${Math.abs(amount).toFixed(2)}`

  if (type === 'income') return `+${normalized}`
  if (type === 'expense') return `-${normalized}`
  if (type === 'transfer') return normalized

  return normalized
}
