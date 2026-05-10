<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";
import * as settingsApi from "../api/settings";
import AppShell from "../components/AppShell.vue";

const baiduRootPath = ref("");
const cacheLimitBytes = ref(0);
const storageBackend = ref<"mock" | "baidu">("mock");
const baiduAuthorizeUrl = ref<string | null>(null);
const baiduHasRefreshToken = ref(false);
const baiduCode = ref("");
const loading = ref(false);
const saving = ref(false);
const authorizing = ref(false);
const message = ref("");
const error = ref("");

function applySettings(settings: {
  baidu_root_path: string;
  cache_limit_bytes: number;
  storage_backend: string;
  baidu_authorize_url: string | null;
  baidu_has_refresh_token: boolean;
}): void {
  baiduRootPath.value = settings.baidu_root_path;
  cacheLimitBytes.value = settings.cache_limit_bytes;
  storageBackend.value = settings.storage_backend === "baidu" ? "baidu" : "mock";
  baiduAuthorizeUrl.value = settings.baidu_authorize_url;
  baiduHasRefreshToken.value = settings.baidu_has_refresh_token;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    applySettings(await settingsApi.fetchSettings());
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "读取设置失败。";
    } else {
      error.value = "读取设置失败。";
    }
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    const updated = await settingsApi.updateSettings({
      baidu_root_path: baiduRootPath.value,
      cache_limit_bytes: cacheLimitBytes.value,
      storage_backend: storageBackend.value,
    });
    applySettings(updated);
    message.value = "设置已保存。";
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "保存设置失败。";
    } else {
      error.value = "保存设置失败。";
    }
  } finally {
    saving.value = false;
  }
}

async function authorizeBaidu(): Promise<void> {
  if (!baiduCode.value.trim()) {
    error.value = "请先粘贴百度授权码。";
    return;
  }

  authorizing.value = true;
  error.value = "";
  message.value = "";
  try {
    const updated = await settingsApi.authorizeBaidu(baiduCode.value.trim());
    applySettings(updated);
    baiduCode.value = "";
    message.value = "百度授权已保存。";
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "百度授权失败。";
    } else {
      error.value = "百度授权失败。";
    }
  } finally {
    authorizing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppShell>
    <div class="page-stack">
      <section class="surface section-card">
        <div class="section-heading">
          <div>
            <div class="eyebrow">Runtime</div>
            <h1>系统设置</h1>
          </div>
        </div>

        <p class="muted">
          敏感 Baidu 凭据仍由后端环境变量管理；这里仅编辑公开运行参数与授权状态。
        </p>

        <p v-if="loading" class="muted">加载中...</p>
        <p v-if="error" class="error banner-message">{{ error }}</p>
        <p v-if="message" class="banner-message success">{{ message }}</p>

        <div class="settings-grid">
          <div class="field">
            <label for="storage-backend">Storage Backend</label>
            <select id="storage-backend" v-model="storageBackend">
              <option value="mock">mock</option>
              <option value="baidu">baidu</option>
            </select>
          </div>

          <div class="field">
            <label for="baidu-root-path">Baidu Root Path</label>
            <input id="baidu-root-path" v-model="baiduRootPath" />
          </div>

          <div class="field">
            <label for="cache-limit-bytes">Cache Limit Bytes</label>
            <input id="cache-limit-bytes" v-model.number="cacheLimitBytes" type="number" min="1" />
          </div>
        </div>

        <div class="button-row">
          <button class="button" type="button" :disabled="saving" @click="submit">
            {{ saving ? "保存中..." : "保存设置" }}
          </button>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-heading">
          <div>
            <div class="eyebrow">OAuth</div>
            <h2>百度授权</h2>
          </div>
          <span class="status-badge" :class="baiduHasRefreshToken ? 'completed' : 'queued'">
            {{ baiduHasRefreshToken ? "已配置" : "未配置" }}
          </span>
        </div>

        <p v-if="baiduAuthorizeUrl" class="muted">
          打开授权页，复制返回的 code，再粘贴到下面输入框中保存。
        </p>
        <p v-else class="muted">当前环境未配置 BAIDU_APP_KEY，无法生成授权链接。</p>

        <div class="button-row">
          <a v-if="baiduAuthorizeUrl" :href="baiduAuthorizeUrl" target="_blank" rel="noreferrer" class="button ghost">
            打开百度授权页
          </a>
        </div>

        <div class="field">
          <label for="baidu-code">Authorization Code</label>
          <input id="baidu-code" v-model="baiduCode" placeholder="粘贴百度授权返回的 code" />
        </div>

        <div class="button-row">
          <button
            class="button"
            type="button"
            :disabled="authorizing || !baiduAuthorizeUrl"
            @click="authorizeBaidu"
          >
            {{ authorizing ? "提交中..." : "保存百度授权" }}
          </button>
        </div>
      </section>
    </div>
  </AppShell>
</template>
