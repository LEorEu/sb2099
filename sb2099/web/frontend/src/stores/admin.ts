import { defineStore } from 'pinia'
import { api } from '@/api/client'

export const useAdminStore = defineStore('admin', {
  state: () => ({ authed: false, checked: false }),
  actions: {
    async check(): Promise<boolean> {
      try {
        await api.admin.me()
        this.authed = true
      } catch {
        this.authed = false
      }
      this.checked = true
      return this.authed
    },
    async login(token: string) {
      await api.admin.login(token)
      this.authed = true
      this.checked = true
    },
    async logout() {
      try { await api.admin.logout() } finally { this.authed = false }
    },
  },
})
