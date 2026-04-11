import type { RelationStatus, SocialStatus, SocialUserSummary } from '@/stores/social'

export const statusClassMap: Record<SocialStatus, string> = {
  combat: 'bg-amber-500',
  online: 'bg-emerald-500',
  offline: 'bg-slate-300',
}

export const statusTextMap: Record<SocialStatus, string> = {
  combat: '闯塔中',
  online: '在线',
  offline: '离线',
}

export const relationTextMap: Record<RelationStatus, string> = {
  none: '可添加',
  accepted: '已是好友',
  outgoing_pending: '已发送',
  incoming_pending: '等待处理',
}

export function displayName(user: SocialUserSummary) {
  return user.nickname || user.username
}

export function getInitials(user: { nickname?: string | null; username: string }) {
  return (user.nickname || user.username).slice(0, 1).toUpperCase()
}

function hasExplicitTimezone(value: string) {
  return /(?:Z|[+\-]\d{2}:\d{2})$/i.test(value)
}

export function parseSocialDate(value: string | null | undefined): Date | null {
  if (!value) return null

  const trimmed = value.trim()
  if (!trimmed) return null

  // Backend may return naive UTC timestamps (without timezone suffix).
  // Treat them as UTC to avoid client locale offset errors.
  const normalized = hasExplicitTimezone(trimmed) ? trimmed : `${trimmed}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function getSocialTimestamp(value: string | null | undefined): number | null {
  const date = parseSocialDate(value)
  return date ? date.getTime() : null
}

function pad2(value: number) {
  return value.toString().padStart(2, '0')
}

function formatHourMinute(date: Date) {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

export function formatChatMessageTime(value: string) {
  const date = parseSocialDate(value)
  if (!date) return '--:--'

  const year = date.getFullYear()
  const month = pad2(date.getMonth() + 1)
  const day = pad2(date.getDate())
  const time = formatHourMinute(date)
  const currentYear = new Date().getFullYear()

  return year === currentYear ? `${month}-${day} ${time}` : `${year}-${month}-${day} ${time}`
}

export function formatShortTime(value: string | null) {
  const date = parseSocialDate(value)
  if (!date) return '暂无动态'
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.max(1, Math.floor(diff / 60_000))} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function formatMessagePreview(content: string | null | undefined) {
  if (!content) return '开始聊天吧'
  return content.length > 24 ? `${content.slice(0, 24)}...` : content
}

export function formatLeaderboardStatus(status: string) {
  if (status === 'dead') return '已结束'
  if (status === 'completed_exhausted') return '已通关'
  return '进行中'
}
