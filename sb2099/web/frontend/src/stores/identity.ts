import { defineStore } from 'pinia'
import type { UserHit } from '@/api/types'

const KEY = 'sb2099_identity_v1'

function read(): UserHit | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const p = JSON.parse(raw)
    return p && p.uid ? p as UserHit : null
  } catch {
    return null
  }
}

export const useIdentityStore = defineStore('identity', {
  state: () => ({ me: read() as UserHit | null }),
  actions: {
    set(u: UserHit) { this.me = u; localStorage.setItem(KEY, JSON.stringify(u)) },
    clear() { this.me = null; localStorage.removeItem(KEY) },
  },
})
