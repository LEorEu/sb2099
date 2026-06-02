<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import TopBar from '@/components/TopBar.vue'
import ToastHost from '@/components/ToastHost.vue'
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'
import { useFavoritesStore } from '@/stores/favorites'
import { useTagsStore } from '@/stores/tags'

const route = useRoute()
const isAdmin = computed(() => !!route.meta.admin)

const favs = useFavoritesStore()
const tags = useTagsStore()
const drawerOpen = ref(false)
const favCount = computed(() => favs.totalCount)

function loadPublicTags() { if (!isAdmin.value) tags.load() }
onMounted(loadPublicTags)
watch(isAdmin, loadPublicTags)
</script>
<template>
  <!-- 后台：独立外壳（自带导航），公开前台的 TopBar/收藏夹不出现 -->
  <template v-if="isAdmin">
    <router-view />
    <ToastHost />
  </template>
  <!-- 公开前台 -->
  <template v-else>
    <TopBar :fav-count="favCount" @open-favorites="drawerOpen = true" />
    <main><router-view /></main>
    <FavoritesDrawer v-model:open="drawerOpen" />
    <ToastHost />
  </template>
</template>
