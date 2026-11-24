import React from 'react';
import Editor from '@monaco-editor/react';

const LARGE_PASTE = 200; // characters

export default function CodeEditor({ language, value, onChange, onLargePaste, readOnly = false, height = '420px' }) {
    const handleMount = (editor) => {
        editor.onDidPaste((e) => {
            const pasted = editor.getModel()?.getValueInRange(e.range) || '';
            if (pasted.length >= LARGE_PASTE && onLargePaste) onLargePaste();
        });
    };

    return (
        <div className="rounded-xl overflow-hidden border border-outline-variant">
            <Editor
                height={height}
                language={language}
                value={value}
                onChange={(v) => onChange && onChange(v ?? '')}
                onMount={handleMount}
                loading={<div className="p-4 text-sm text-on-surface-variant">Loading editor...</div>}
                options={{
                    readOnly,
                    minimap: { enabled: false },
                    fontSize: 14,
                    tabSize: 4,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    wordWrap: 'on',
                }}
            />
        </div>
    );
}
