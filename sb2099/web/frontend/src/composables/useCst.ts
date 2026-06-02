// 后端返回的是 UTC naive datetime 的 ISO 串（无时区），统一 +8 转 CST 展示。
export function cst(iso: string | null | undefined, withYear = false): string {
  if (!iso) return ''
  const head = String(iso).split('.')[0] // 去微秒
  const d = new Date(head + 'Z') // 当作 UTC 解析
  if (Number.isNaN(d.getTime())) return ''
  const c = new Date(d.getTime() + 8 * 3600 * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  const mm = p(c.getUTCMonth() + 1), dd = p(c.getUTCDate())
  const hh = p(c.getUTCHours()), mi = p(c.getUTCMinutes())
  return withYear
    ? `${c.getUTCFullYear()}-${mm}-${dd} ${hh}:${mi}`
    : `${mm}-${dd} ${hh}:${mi}`
}
