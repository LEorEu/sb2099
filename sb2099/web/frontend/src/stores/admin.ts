import { defineStore } from 'pinia'
import { api } from '@/api/client'

interface Summary { pending: number; open_reports: number; library_total: number }

export const useAdminStore = defineStore('admin', {
  state: () => ({
    authed: false,
    checked: false,
    summary: { pending: 0, open_reports: 0, library_total: 0 } as Summary,
  }),
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
    async loadSummary() {
      try { this.summary = await api.admin.getSummary() } catch { /* ignore */ }
    },
  },
})
