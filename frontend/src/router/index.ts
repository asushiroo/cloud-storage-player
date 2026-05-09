import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import LibraryView from "../views/LibraryView.vue";
import VideoDetailView from "../views/VideoDetailView.vue";
import SettingsView from "../views/SettingsView.vue";
import { pinia } from "../stores/pinia";
import { useSessionStore } from "../stores/session";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/library",
    },
    {
      path: "/login",
      name: "login",
      component: LoginView,
    },
    {
      path: "/library",
      name: "library",
      component: LibraryView,
      meta: { requiresAuth: true },
    },
    {
      path: "/videos/:videoId",
      name: "video-detail",
      component: VideoDetailView,
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsView,
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach(async (to) => {
  const sessionStore = useSessionStore(pinia);
  if (!sessionStore.loaded) {
    await sessionStore.refresh();
  }

  if (to.meta.requiresAuth && !sessionStore.authenticated) {
    return { name: "login" };
  }

  if (to.name === "login" && sessionStore.authenticated) {
    return { name: "library" };
  }

  return true;
});

export default router;
