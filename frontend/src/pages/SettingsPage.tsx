import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { authorizeBaidu, fetchSettings, updateSettings, type SettingsUpdatePayload } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError, PublicSettings } from "../types/api";
import { formatBytes } from "../utils/format";

const DEFAULT_TRANSFER_CONCURRENCY = "5";
const DEFAULT_BAIDU_ROOT_PATH = "/apps/CloudStoragePlayer";
const DEFAULT_SEGMENT_CACHE_ROOT_PATH = "data/segments";
const DEFAULT_CACHE_LIMIT_BYTES = String(2 * 1024 * 1024 * 1024);

const resolveTransferConcurrency = (
  primary: number | undefined,
  legacy: number | undefined,
  fallback: string,
): string => {
  if (typeof primary === "number" && Number.isFinite(primary)) {
    return String(primary);
  }
  if (typeof legacy === "number" && Number.isFinite(legacy)) {
    return String(legacy);
  }
  return fallback;
};

const hasSplitConcurrencyFields = (settings: PublicSettings | undefined): boolean =>
  typeof settings?.upload_transfer_concurrency === "number" &&
  typeof settings?.download_transfer_concurrency === "number";

const hasLegacyConcurrencyField = (settings: PublicSettings | undefined): boolean =>
  typeof settings?.remote_transfer_concurrency === "number";

interface SettingInputFieldProps {
  value: string;
  hint: string;
  onChange: (value: string) => void;
  inputMode?: "text" | "numeric";
  type?: "text" | "number";
  min?: number;
  max?: number;
}

function SettingInputField({ value, hint, onChange, inputMode, type = "text", min, max }: SettingInputFieldProps) {
  return (
    <label className="setting-input-shell">
      <input
        className="text-input"
        inputMode={inputMode}
        max={max}
        min={min}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
      <span className="setting-input-hint" role="note">
        {hint}
      </span>
    </label>
  );
}

export function SettingsPage() {
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: session.data?.authenticated === true,
  });

  const [storageBackend, setStorageBackend] = useState("mock");
  const [baiduRootPath, setBaiduRootPath] = useState(DEFAULT_BAIDU_ROOT_PATH);
  const [segmentCacheRootPath, setSegmentCacheRootPath] = useState(DEFAULT_SEGMENT_CACHE_ROOT_PATH);
  const [cacheLimitBytes, setCacheLimitBytes] = useState(DEFAULT_CACHE_LIMIT_BYTES);
  const [uploadTransferConcurrency, setUploadTransferConcurrency] = useState(DEFAULT_TRANSFER_CONCURRENCY);
  const [downloadTransferConcurrency, setDownloadTransferConcurrency] = useState(DEFAULT_TRANSFER_CONCURRENCY);
  const [oauthCode, setOauthCode] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applySettingsToForm = (settings: PublicSettings) => {
    setStorageBackend(settings.storage_backend);
    setBaiduRootPath(settings.baidu_root_path);
    setSegmentCacheRootPath(settings.segment_cache_root_path);
    setCacheLimitBytes(String(settings.cache_limit_bytes));
    setUploadTransferConcurrency((current) =>
      resolveTransferConcurrency(
        settings.upload_transfer_concurrency,
        settings.remote_transfer_concurrency,
        current || DEFAULT_TRANSFER_CONCURRENCY,
      ),
    );
    setDownloadTransferConcurrency((current) =>
      resolveTransferConcurrency(
        settings.download_transfer_concurrency,
        settings.remote_transfer_concurrency,
        current || DEFAULT_TRANSFER_CONCURRENCY,
      ),
    );
  };

  useEffect(() => {
    if (!settingsQuery.data) return;
    applySettingsToForm(settingsQuery.data);
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const uploadConcurrency = Number(uploadTransferConcurrency);
      const downloadConcurrency = Number(downloadTransferConcurrency);
      const payload: SettingsUpdatePayload = {
        storage_backend: storageBackend,
        baidu_root_path: baiduRootPath,
        segment_cache_root_path: segmentCacheRootPath,
        cache_limit_bytes: Number(cacheLimitBytes),
        upload_transfer_concurrency: uploadConcurrency,
        download_transfer_concurrency: downloadConcurrency,
      };

      if (!hasSplitConcurrencyFields(settingsQuery.data) && hasLegacyConcurrencyField(settingsQuery.data)) {
        if (uploadConcurrency !== downloadConcurrency) {
          const conflict: ApiError = {
            status: 409,
            message:
              "当前后端进程仍是旧版本，只支持单一并发字段。请先重启后端，再分别保存上传并发和下载并发。",
          };
          throw conflict;
        }
        payload.remote_transfer_concurrency = uploadConcurrency;
      }

      return updateSettings(payload);
    },
    onSuccess: async (savedSettings) => {
      queryClient.setQueryData(["settings"], savedSettings);
      applySettingsToForm(savedSettings);
      setFeedback("设置已保存。");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const oauthMutation = useMutation({
    mutationFn: () => authorizeBaidu(oauthCode),
    onSuccess: async () => {
      setFeedback("百度 OAuth code 已提交。");
      setError(null);
      setOauthCode("");
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在加载设置...</p>;
  }
  if (settingsQuery.isLoading && !settingsQuery.data) {
    return <p className="state-text">正在加载设置...</p>;
  }

  const settings = settingsQuery.data;
  const currentUploadConcurrency = resolveTransferConcurrency(
    settings?.upload_transfer_concurrency,
    settings?.remote_transfer_concurrency,
    uploadTransferConcurrency || DEFAULT_TRANSFER_CONCURRENCY,
  );
  const currentDownloadConcurrency = resolveTransferConcurrency(
    settings?.download_transfer_concurrency,
    settings?.remote_transfer_concurrency,
    downloadTransferConcurrency || DEFAULT_TRANSFER_CONCURRENCY,
  );
  const backendIsLegacyConcurrencyOnly =
    !hasSplitConcurrencyFields(settings) && hasLegacyConcurrencyField(settings);

  return (
    <div className="page-stack">
      {error ? (
        <Surface>
          <p className="error-text">{error}</p>
        </Surface>
      ) : null}
      {feedback ? (
        <Surface>
          <p>{feedback}</p>
        </Surface>
      ) : null}

      <Surface>
        <h2>运行配置</h2>
        <div className="form-stack">
          <SettingInputField
            hint="mock 或 baidu"
            onChange={setStorageBackend}
            value={storageBackend}
          />
          <SettingInputField
            hint="Baidu 根路径，例如 /apps/CloudStoragePlayer"
            onChange={setBaiduRootPath}
            value={baiduRootPath}
          />
          <SettingInputField
            hint="缓存目录，例如 D:/cache/segments"
            onChange={setSegmentCacheRootPath}
            value={segmentCacheRootPath}
          />
          <SettingInputField
            hint="缓存字节上限"
            inputMode="numeric"
            onChange={setCacheLimitBytes}
            value={cacheLimitBytes}
          />
          <SettingInputField
            hint="上传并发数，范围 1 到 32"
            inputMode="numeric"
            max={32}
            min={1}
            onChange={setUploadTransferConcurrency}
            type="number"
            value={uploadTransferConcurrency}
          />
          <SettingInputField
            hint="下载并发数，范围 1 到 32"
            inputMode="numeric"
            max={32}
            min={1}
            onChange={setDownloadTransferConcurrency}
            type="number"
            value={downloadTransferConcurrency}
          />
          <button
            className="primary-button"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
            type="button"
          >
            {saveMutation.isPending ? "保存中..." : "保存设置"}
          </button>
        </div>
        {backendIsLegacyConcurrencyOnly ? (
          <p className="error-text">
            当前连接到的后端仍只支持旧的单并发字段。要分别保存上传并发和下载并发，请先重启后端到最新代码。
          </p>
        ) : null}
      </Surface>

      <div className="section-divider" />

      <Surface>
        <h2>百度授权</h2>
        <p className="muted">首次接入百度仍需管理员手动完成一次 OAuth 授权码流程。</p>
        {settings?.baidu_authorize_url ? (
          <a className="primary-button link-button" href={settings.baidu_authorize_url} rel="noreferrer" target="_blank">
            打开百度授权页
          </a>
        ) : (
          <p className="muted">当前没有可用授权链接，请先到 `/admin` 管理员页面填写百度 App Key / Secret Key。</p>
        )}
        <div className="form-stack top-gap">
          <input
            className="text-input"
            onChange={(event) => setOauthCode(event.target.value)}
            placeholder="粘贴百度返回的 code"
            value={oauthCode}
          />
          <button
            className="primary-button"
            disabled={oauthMutation.isPending || oauthCode.trim().length === 0}
            onClick={() => oauthMutation.mutate()}
            type="button"
          >
            {oauthMutation.isPending ? "提交中..." : "提交 OAuth code"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: "1rem" }}>
          Refresh Token 状态：{settings?.baidu_has_refresh_token ? "已存在" : "未配置"}
        </p>
      </Surface>
    </div>
  );
}
