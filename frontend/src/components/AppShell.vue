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
    <div class="app-backdrop">
      <div class="backdrop-orb orb-one" />
      <div class="backdrop-orb orb-two" />
      <div class="backdrop-orb orb-three" />
    </div>

    <header class="topbar">
      <RouterLink to="/library" class="brand-lockup">
        <div class="brand-mark">CSP</div>
        <div>
          <strong>Cloud Storage Player</strong>
          <p>Kyoo 风格重构 · Vue 前端</p>
        </div>
      </RouterLink>

      <nav class="nav-links">
        <RouterLink to="/library" class="nav-link">媒体库</RouterLink>
        <RouterLink to="/settings" class="nav-link">设置</RouterLink>
      </nav>

      <div class="topbar-actions">
        <span class="session-indicator">LAN Session</span>
        <button class="button ghost" type="button" @click="handleLogout">退出</button>
      </div>
    </header>

    <main class="page-container">
      <slot />
    </main>
  </div>
</template>
