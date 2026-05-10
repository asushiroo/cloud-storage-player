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
    <div class="app-backdrop">
      <div class="backdrop-orb orb-one" />
      <div class="backdrop-orb orb-two" />
      <div class="backdrop-orb orb-three" />
    </div>

    <section class="login-card surface">
      <div class="eyebrow">Cloud Storage Player</div>
      <h1>进入你的私人影库</h1>
      <p class="muted">
        参考 third/Kyoo 的视觉风格，重新整理了登录页、媒体库、播放详情和标签体验。
      </p>

      <div class="field">
        <label for="password">共享密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="输入共享密码"
          @keyup.enter="submit"
        />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="button-row">
        <button class="button" type="button" :disabled="loading" @click="submit">
          {{ loading ? "登录中..." : "进入媒体库" }}
        </button>
      </div>
    </section>
  </div>
</template>
