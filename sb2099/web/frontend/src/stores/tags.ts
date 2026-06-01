import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { Tag } from '@/api/types'

export const useTagsStore = defineStore('tags', {
  state: () => ({ list: [] as Tag[], loaded: false }),
  getters: {
    map: (s) => Object.fromEntries(s.list.map(t => [t.value, t.label])) as Record<string, string>,
  },
  actions: {
    async load() {
      if (this.loaded) return
      this.list = await api.getTags()
      this.loaded = true
    },
    labelOf(value: string): string {
      return this.map[value] ?? value
    },
  },
})
