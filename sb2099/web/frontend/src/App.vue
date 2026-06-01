<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import TopBar from '@/components/TopBar.vue'
import ToastHost from '@/components/ToastHost.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useTagsStore } from '@/stores/tags'

const favs = useFavoritesStore()
const tags = useTagsStore()
const drawerOpen = ref(false)
const favCount = computed(() => favs.totalCount)
onMounted(() => tags.load())
</script>
<template>
  <TopBar :fav-count="favCount" @open-favorites="drawerOpen = true" />
  <main><router-view /></main>
  <!-- FavoritesDrawer 在 Task 15 接入 -->
  <ToastHost />
</template>
