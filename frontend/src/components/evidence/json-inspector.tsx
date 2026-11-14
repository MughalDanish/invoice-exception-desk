"use client";
import { useRef, useState } from "react";
import { Copy } from "lucide-react";
import { Button } from "../ui/button";
export function JsonInspector({ value }: { value: unknown }) {
  const pre = useRef<HTMLPreElement>(null);
  const [status, setStatus] = useState("");
  const json = JSON.stringify(value, null, 2);
  const tokens = (json ?? "No payload supplied").split(
    /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
  );
  async function copy() {
    try {
      await navigator.clipboard.writeText(json ?? "");
      setStatus("JSON copied.");
    } catch {
      setStatus(
        "Clipboard unavailable. Use Select JSON, then copy the selected text.",
      );
    }
  }
  function select() {
    if (!pre.current) return;
    const range = document.createRange();
    range.selectNodeContents(pre.current);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    setStatus("JSON selected. Use your browser's Copy command.");
  }
  return (
    <div className="json-inspector">
      <p className="muted">Complete preserved data. Read only.</p>
      <div className="technical-actions">
        <Button
          variant="outline"
          size="sm"
          onClick={copy}
          disabled={json === undefined}
        >
          <Copy className="size-4" />
          Copy JSON
        </Button>
        <Button variant="ghost" size="sm" onClick={select}>
          Select JSON
        </Button>
      </div>
      <p role="status" className="copy-status">
        {status}
      </p>
      <pre ref={pre} tabIndex={0} aria-label="Preserved technical JSON">
        {tokens.map((token, i) => (
          <span
            key={i}
            className={
              /^".*"\s*:$/.test(token)
                ? "json-key"
                : /^"/.test(token)
                  ? "json-string"
                  : /^(true|false|null|-?\d)/.test(token)
                    ? "json-literal"
                    : undefined
            }
          >
            {token}
          </span>
        ))}
      </pre>
    </div>
  );
}
