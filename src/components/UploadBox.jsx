// src/components/UploadBox.jsx
import React, { useRef, useState } from "react";

export default function UploadBox({ label, onFile }) {
  const ref = useRef();
  const [name, setName] = useState("");
  const [dragging, setDragging] = useState(false);

  function handleFile(file) {
    if (!file) return;
    setName(file.name);
    onFile && onFile(file);
  }

  function change(e) {
    const f = e.target.files?.[0];
    handleFile(f);
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
    const f = e.dataTransfer?.files?.[0];
    handleFile(f);
  }

  return (
    <div
      className={`uploadbox ${dragging ? "dragging" : ""}`}
      onDragOver={onDragOver}
      onDragEnter={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => ref.current?.click()}
    >
      <div className="uplabel">{label}</div>
      <div className="drophint">
        Drop a file here or <span className="browse">browse</span>
      </div>
      {name && <div className="filename">Selected: {name}</div>}
      <input ref={ref} type="file" onChange={change} hidden />
    </div>
  );
}
