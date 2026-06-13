import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download, Copy, Check } from 'lucide-react';

export default function Preview({ jobId }: { jobId: string }) {
  const [content, setContent] = useState<string>('Loading...');
  const [filename, setFilename] = useState<string>('');
  const [copied, setCopied] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    fetch(`/api/v1/jobs/${jobId}/result`)
      .then(res => res.json())
      .then(data => {
        setContent(data.markdown || '# Error: No markdown content');
        setFilename(data.input_filename || '');
      })
      .catch(() => setContent('# Error loading preview'));
  }, [jobId]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    let outName = `document_${jobId.substring(0, 8)}.md`;
    if (filename) {
      const parts = filename.split('.');
      parts.pop();
      outName = `${parts.join('.')}.md`;
    }
    a.download = outName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-6">
          <h2 className="text-2xl font-bold text-gray-800">Document Preview</h2>
          <div className="flex bg-gray-100 rounded-lg p-1 border border-gray-200">
            <button 
              onClick={() => setShowRaw(false)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${!showRaw ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
            >
              Rendered
            </button>
            <button 
              onClick={() => setShowRaw(true)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${showRaw ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
            >
              Raw MD
            </button>
          </div>
        </div>
        
        <div className="flex gap-3">
          <button onClick={copyToClipboard} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition">
            {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Copied!' : 'Copy MD'}
          </button>
          <button onClick={handleDownload} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition">
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>
      </div>
      
      <div className="h-[70vh]">
        {showRaw ? (
          <div className="flex flex-col h-full border rounded-xl overflow-hidden shadow-sm bg-gray-50">
            <textarea 
              readOnly 
              value={content} 
              className="flex-1 p-6 bg-transparent resize-none outline-none font-mono text-sm text-gray-800"
            />
          </div>
        ) : (
          <div className="flex flex-col h-full border rounded-xl overflow-hidden shadow-sm bg-white">
            <div className="flex-1 p-8 overflow-y-auto prose prose-blue max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
