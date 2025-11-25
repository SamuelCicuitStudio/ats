// src/components/UploadBox.jsx
import React, { useRef, useState } from "react";

export default function UploadBox({ label, onFile }) {
  const ref = useRef();
  const [name, setName] = useState("");

  function change(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setName(f.name);
    onFile && onFile(f);
  }

  return (
    <div className="uploadbox">
      <label className="uplabel">{label}</label>
      <input ref={ref} type="file" onChange={change} />
      {name && <div className="filename">{name}</div>}
    </div>
  );
}
