// =============================================================================
// PH Agent Hub — CodeEditor Component
// =============================================================================
// Wraps @uiw/react-codemirror with Python language support and a dark theme
// matching the admin area aesthetic.
// =============================================================================

import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";

interface CodeEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
  placeholder?: string;
}

export function CodeEditor({
  value = "",
  onChange,
  readOnly = false,
  height = "300px",
  placeholder = "Write your Python code here...",
}: CodeEditorProps) {
  return (
    <CodeMirror
      value={value}
      height={height}
      theme="dark"
      extensions={[python()]}
      onChange={(val) => onChange?.(val)}
      readOnly={readOnly}
      placeholder={placeholder}
      basicSetup={{
        lineNumbers: true,
        foldGutter: true,
        highlightActiveLine: true,
        autocompletion: true,
        bracketMatching: true,
        closeBrackets: true,
        indentOnInput: true,
      }}
    />
  );
}

export default CodeEditor;
