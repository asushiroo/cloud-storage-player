<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";

const router = useRouter();
const sessionStore = useSessionStore();

const password = ref("");
const loading = ref(false);
const error = ref("");

async function submit(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    await sessionStore.login(password.value);
    await router.push({ name: "library" });
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "登录失败。";
    } else {
      error.value = "登录失败。";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <section class="panel login-card stack">
      <div>
        <h1>Cloud Storage Player</h1>
        <p class="muted">使用共享密码登录局域网视频服务。</p>
      </div>

      <div class="field">
        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          @keyup.enter="submit"
        />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="button-row">
        <button class="button" type="button" :disabled="loading" @click="submit">
          {{ loading ? "登录中..." : "登录" }}
        </button>
      </div>
    </section>
  </div>
</template>
