// src/components/UploadBox.jsx
import React, { useRef, useState } from "react";

export default function UploadBox({
  label,
  onFile,
  onFiles,
  multiple = false,
  maxFiles,
  accept,
  helper,
}) {
  const ref = useRef();
  const [name, setName] = useState("");
  const [dragging, setDragging] = useState(false);

  function handleFiles(fileList) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;

    const originalCount = files.length;
    const capped =
      multiple && maxFiles ? files.slice(0, maxFiles) : files.slice(0);
    const labelCount =
      multiple && maxFiles ? Math.min(originalCount, maxFiles) : capped.length;
    const labelStr =
      labelCount > 1
        ? `${labelCount} files selected`
        : capped[0]?.name || "";

    setName(labelStr);
    if (multiple && onFiles) {
      onFiles(capped, originalCount);
    } else if (capped[0] && onFile) {
      onFile(capped[0], originalCount);
    }
  }

  function change(e) {
    handleFiles(e.target.files);
  }

  function onDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }
  function onDragLeave(e) {
    e.preventDefault();
    setDragging(false);
  }
  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer?.files);
  }

  return (
    <div
      className={`uploadbox ${dragging ? "dragging" : ""}`}
      onDragOver={onDragOver}
      onDragEnter={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => ref.current?.click()}
      role="button"
    >
      <div className="card-body text-center">
        <svg
          className="icon"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M12 16V4" strokeLinecap="round" />
          <path d="M7 9l5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>{label}</div>
        <a
          className="btn"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            ref.current?.click();
          }}
        >
          Browse files
        </a>
        <div className="muted" style={{ marginTop: 8 }}>
          {helper || "Drag & drop or browse"}
        </div>
        {name && (
          <div className="filename mt-2 text-secondary small">Selected: {name}</div>
        )}
        <input
          ref={ref}
          type="file"
          onChange={change}
          hidden
          multiple={multiple}
          accept={accept}
        />
      </div>
    </div>
  );
}
