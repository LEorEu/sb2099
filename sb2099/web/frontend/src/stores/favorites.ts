import { defineStore } from 'pinia'

const KEY = 'sb2099_favorites_v1'
interface FavState { groups: Record<string, number[]>; order: string[] }

function read(): FavState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { groups: { 默认: [] }, order: ['默认'] }
    const p = JSON.parse(raw)
    if (!p.groups || !p.order) throw new Error('bad')
    return p
  } catch {
    return { groups: { 默认: [] }, order: ['默认'] }
  }
}

export const useFavoritesStore = defineStore('favorites', {
  state: () => read() as FavState,
  getters: {
    totalCount: (s) => Object.values(s.groups).reduce((a, g) => a + g.length, 0),
    has: (s) => (id: number) => Object.values(s.groups).some(g => g.includes(id)),
  },
  actions: {
    persist() { localStorage.setItem(KEY, JSON.stringify({ groups: this.groups, order: this.order })) },
    addGroup(name: string) {
      name = name.trim()
      if (!name || this.groups[name]) return
      this.groups[name] = []; this.order.push(name); this.persist()
    },
    add(id: number, group = '默认') {
      if (!this.groups[group]) this.addGroup(group)
      if (!this.groups[group].includes(id)) { this.groups[group].push(id); this.persist() }
    },
    remove(id: number, group: string) {
      const arr = this.groups[group]; if (!arr) return
      const i = arr.indexOf(id); if (i >= 0) { arr.splice(i, 1); this.persist() }
    },
    move(id: number, from: string, to: string) {
      if (from === to) return
      const src = this.groups[from]
      if (!src) return
      const i = src.indexOf(id)
      if (i < 0) return
      src.splice(i, 1)
      if (!this.groups[to]) this.addGroup(to)
      if (!this.groups[to].includes(id)) this.groups[to].push(id)
      this.persist()
    },
    removeEverywhere(id: number) {
      let hit = false
      for (const g of Object.values(this.groups)) {
        const i = g.indexOf(id); if (i >= 0) { g.splice(i, 1); hit = true }
      }
      if (hit) this.persist()
    },
    exportJson(): string { return JSON.stringify({ groups: this.groups, order: this.order }) },
    importJson(raw: string): boolean {
      try {
        const p = JSON.parse(raw)
        if (!p.groups || !p.order) return false
        this.groups = p.groups; this.order = p.order; this.persist(); return true
      } catch { return false }
    },
  },
})
