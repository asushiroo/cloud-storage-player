<script setup lang="ts">
import { useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";

const router = useRouter();
const sessionStore = useSessionStore();

async function handleLogout(): Promise<void> {
  await sessionStore.logout();
  await router.push({ name: "login" });
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <h1>Cloud Storage Player</h1>
      <p class="muted">前后端分离 / Vue 前端</p>
      <nav>
        <RouterLink to="/library">媒体库</RouterLink>
        <RouterLink to="/settings">设置</RouterLink>
      </nav>
      <div class="button-row" style="margin-top: 1.5rem;">
        <button class="button secondary" type="button" @click="handleLogout">
          退出登录
        </button>
      </div>
    </aside>

    <main class="main">
      <slot />
    </main>
  </div>
</template>
