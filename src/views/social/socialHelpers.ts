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

export function formatShortTime(value: string | null) {
  if (!value) return '暂无动态'
  const date = new Date(value)
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
