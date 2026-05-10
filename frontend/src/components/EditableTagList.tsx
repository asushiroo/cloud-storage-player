import { useEffect, useMemo, useState } from "react";
import { TagChip } from "./TagChip";

interface EditableTagListProps {
  disabled?: boolean;
  tags: string[];
  onSave: (tags: string[]) => Promise<void> | void;
}

const normalizeTags = (tags: string[]) => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const tag of tags) {
    const value = tag.trim();
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
  return normalized;
};

export function EditableTagList({ disabled = false, tags, onSave }: EditableTagListProps) {
  const [draftTags, setDraftTags] = useState(tags);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setDraftTags(tags);
    setEditingIndex(null);
    setEditingValue("");
    setIsAdding(false);
  }, [tags]);

  const hasTags = useMemo(() => draftTags.length > 0, [draftTags]);

  const commitTags = async (nextTags: string[]) => {
    const normalized = normalizeTags(nextTags);
    setDraftTags(normalized);
    setIsSaving(true);
    try {
      await onSave(normalized);
    } finally {
      setIsSaving(false);
    }
  };

  const removeTag = async (index: number) => {
    const nextTags = draftTags.filter((_, currentIndex) => currentIndex !== index);
    await commitTags(nextTags);
  };

  const commitEditing = async () => {
    if (editingIndex === null) {
      return;
    }
    const nextTags = [...draftTags];
    const trimmedValue = editingValue.trim();
    if (!trimmedValue) {
      nextTags.splice(editingIndex, 1);
    } else {
      nextTags[editingIndex] = trimmedValue;
    }
    setEditingIndex(null);
    setEditingValue("");
    await commitTags(nextTags);
  };

  const commitAdd = async () => {
    const trimmedValue = editingValue.trim();
    setIsAdding(false);
    setEditingValue("");
    if (!trimmedValue) {
      return;
    }
    await commitTags([...draftTags, trimmedValue]);
  };

  return (
    <div className="editable-tag-panel">
      <div className="editable-tag-row">
        {draftTags.map((tag, index) =>
          editingIndex === index ? (
            <input
              autoFocus
              className="tag-input-chip"
              disabled={disabled || isSaving}
              key={`${tag}-${index}`}
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
                  setEditingIndex(null);
                  setEditingValue("");
                }
              }}
              value={editingValue}
            />
          ) : (
            <div className="editable-tag-chip" key={`${tag}-${index}`}>
              <div
                onDoubleClick={() => {
                  if (disabled || isSaving) {
                    return;
                  }
                  setEditingIndex(index);
                  setEditingValue(tag);
                  setIsAdding(false);
                }}
              >
                <TagChip label={tag} small />
              </div>
              <button
                className="tag-chip-remove"
                disabled={disabled || isSaving}
                onClick={() => {
                  void removeTag(index);
                }}
                title="删除标签"
                type="button"
              >
                ×
              </button>
            </div>
          ),
        )}
        {isAdding ? (
          <input
            autoFocus
            className="tag-input-chip"
            disabled={disabled || isSaving}
            onBlur={() => {
              void commitAdd();
            }}
            onChange={(event) => setEditingValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void commitAdd();
              }
              if (event.key === "Escape") {
                setIsAdding(false);
                setEditingValue("");
              }
            }}
            placeholder="新标签"
            value={editingValue}
          />
        ) : (
          <button
            className="tag-add-chip"
            disabled={disabled || isSaving}
            onClick={() => {
              setIsAdding(true);
              setEditingIndex(null);
              setEditingValue("");
            }}
            type="button"
          >
            + 添加标签
          </button>
        )}
      </div>
      {!hasTags ? <p className="muted small-text">暂无标签，点击“添加标签”开始。</p> : null}
      <p className="muted small-text">双击标签可编辑，右上角 × 可删除；如需二级分类可使用“一级/二级”格式，修改后会自动保存。</p>
    </div>
  );
}
