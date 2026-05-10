import { useEffect, useMemo, useState } from "react";
import { buildPrimaryTagValue, buildSecondaryTagValue, expandTagValue } from "../utils/tagHierarchy";
import { TagChip } from "./TagChip";

interface EditableTagListProps {
  disabled?: boolean;
  tags: string[];
  onSave: (tags: string[]) => Promise<void> | void;
}

type TagLevel = "primary" | "secondary";

const normalizeTags = (tags: string[]) => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const tag of tags) {
    for (const parsed of expandTagValue(tag)) {
      const value = parsed.level === "primary" ? buildPrimaryTagValue(parsed.label) : buildSecondaryTagValue(parsed.label);
      if (!value) {
        continue;
      }
      const key = value.toLocaleLowerCase();
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      normalized.push(value);
    }
  }
  return normalized;
};

function buildInitialPrimary(tags: string[]) {
  return normalizeTags(tags)
    .map((tag) => expandTagValue(tag)[0])
    .filter((tag) => tag.level === "primary")
    .map((tag) => tag.label)
    .filter(Boolean);
}

function buildInitialSecondaries(tags: string[]) {
  return normalizeTags(tags)
    .map((tag) => expandTagValue(tag)[0])
    .filter((tag) => tag.level === "secondary")
    .map((tag) => tag.label)
    .filter(Boolean);
}

function joinLevels(primaryTags: string[], secondaryTags: string[]) {
  return normalizeTags([
    ...primaryTags.map((tag) => buildPrimaryTagValue(tag)),
    ...secondaryTags.map((tag) => buildSecondaryTagValue(tag)),
  ]);
}

export function EditableTagList({ disabled = false, tags, onSave }: EditableTagListProps) {
  const [primaryTags, setPrimaryTags] = useState<string[]>(() => buildInitialPrimary(tags));
  const [secondaryTags, setSecondaryTags] = useState<string[]>(() => buildInitialSecondaries(tags));
  const [editingLevel, setEditingLevel] = useState<TagLevel | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setPrimaryTags(buildInitialPrimary(tags));
    setSecondaryTags(buildInitialSecondaries(tags));
    setEditingLevel(null);
    setEditingIndex(null);
    setEditingValue("");
  }, [tags]);

  const hasTags = useMemo(() => primaryTags.length > 0 || secondaryTags.length > 0, [primaryTags, secondaryTags]);

  const commitTags = async (nextPrimary: string[], nextSecondary: string[]) => {
    const normalizedPrimary = nextPrimary.map((tag) => tag.trim()).filter(Boolean);
    const normalizedSecondary = nextSecondary.map((tag) => tag.trim()).filter(Boolean);
    setPrimaryTags(normalizedPrimary);
    setSecondaryTags(normalizedSecondary);
    setIsSaving(true);
    try {
      await onSave(joinLevels(normalizedPrimary, normalizedSecondary));
    } finally {
      setIsSaving(false);
    }
  };

  const removeTag = async (level: TagLevel, index: number) => {
    const nextPrimary = level === "primary" ? primaryTags.filter((_, currentIndex) => currentIndex !== index) : primaryTags;
    const nextSecondary = level === "secondary" ? secondaryTags.filter((_, currentIndex) => currentIndex !== index) : secondaryTags;
    await commitTags(nextPrimary, nextSecondary);
  };

  const startEditing = (level: TagLevel, index: number, value: string) => {
    if (disabled || isSaving) {
      return;
    }
    setEditingLevel(level);
    setEditingIndex(index);
    setEditingValue(value);
  };

  const commitEditing = async () => {
    if (editingLevel === null || editingIndex === null) {
      return;
    }
    const trimmedValue = editingValue.trim();
    const nextPrimary = [...primaryTags];
    const nextSecondary = [...secondaryTags];
    const targetList = editingLevel === "primary" ? nextPrimary : nextSecondary;
    if (!trimmedValue) {
      targetList.splice(editingIndex, 1);
    } else {
      targetList[editingIndex] = trimmedValue;
    }
    setEditingLevel(null);
    setEditingIndex(null);
    setEditingValue("");
    await commitTags(nextPrimary, nextSecondary);
  };

  const addTag = async (level: TagLevel) => {
    const trimmedValue = editingValue.trim();
    setEditingLevel(null);
    setEditingIndex(null);
    setEditingValue("");
    if (!trimmedValue) {
      return;
    }
    await commitTags(
      level === "primary" ? [...primaryTags, trimmedValue] : primaryTags,
      level === "secondary" ? [...secondaryTags, trimmedValue] : secondaryTags,
    );
  };

  const renderTagRow = (level: TagLevel, title: string, values: string[]) => (
    <div className="editable-tag-section">
      <p className="small-text muted">{title}</p>
      <div className="editable-tag-row">
        {values.map((tag, index) =>
          editingLevel === level && editingIndex === index ? (
            <input
              autoFocus
              className="tag-input-chip"
              disabled={disabled || isSaving}
              key={`${level}-${tag}-${index}`}
              onBlur={() => {
                void commitEditing();
              }}
              onChange={(event) => setEditingValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void commitEditing();
                }
                if (event.key === "Escape") {
                  setEditingLevel(null);
                  setEditingIndex(null);
                  setEditingValue("");
                }
              }}
              value={editingValue}
            />
          ) : (
            <div className="editable-tag-chip" key={`${level}-${tag}-${index}`}>
              <div onDoubleClick={() => startEditing(level, index, tag)}>
                <TagChip label={tag} small />
              </div>
              <button
                className="tag-chip-remove"
                disabled={disabled || isSaving}
                onClick={() => {
                  void removeTag(level, index);
                }}
                title="删除标签"
                type="button"
              >
                ×
              </button>
            </div>
          ),
        )}
        {editingLevel === level && editingIndex === values.length ? (
          <input
            autoFocus
            className="tag-input-chip"
            disabled={disabled || isSaving}
            onBlur={() => {
              void addTag(level);
            }}
            onChange={(event) => setEditingValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void addTag(level);
              }
              if (event.key === "Escape") {
                setEditingLevel(null);
                setEditingIndex(null);
                setEditingValue("");
              }
            }}
            placeholder={level === "primary" ? "新增一级标签" : "新增二级标签"}
            value={editingValue}
          />
        ) : (
          <button
            className="tag-add-chip"
            disabled={disabled || isSaving || (level === "secondary" && primaryTags.length === 0)}
            onClick={() => {
              setEditingLevel(level);
              setEditingIndex(values.length);
              setEditingValue("");
            }}
            type="button"
          >
            {level === "primary" ? "+ 添加一级标签" : "+ 添加二级标签"}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="editable-tag-panel">
      {renderTagRow("primary", "一级标签", primaryTags)}
      {renderTagRow("secondary", "二级标签", secondaryTags)}
      {!hasTags ? <p className="muted small-text">暂无标签，点击上方按钮开始。</p> : null}
      <p className="muted small-text">双击标签可编辑，右上角 × 可删除；一级与二级标签会分开保存与展示。</p>
    </div>
  );
}
