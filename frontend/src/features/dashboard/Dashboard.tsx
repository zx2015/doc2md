import React, { useState, useEffect } from 'react';
import { UploadCloud, CheckCircle, Clock, Loader, XCircle } from 'lucide-react';

type QueueItem = {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'queued' | 'failed';
  jobId?: string;
  error?: string;
};

// Fallback for insecure contexts (HTTP) where crypto.randomUUID is undefined
const generateId = () => {
  return typeof crypto !== 'undefined' && crypto.randomUUID 
    ? crypto.randomUUID() 
    : Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
};

export default function Dashboard({ onJobComplete }: { onJobComplete?: (jobId: string) => void }) {
  const [uploadQueue, setUploadQueue] = useState<QueueItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());

  // 意外离开保护
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isUploading) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isUploading]);

  const fetchRecentJobs = () => {
    fetch('/api/v1/jobs?limit=20')
      .then(res => res.json())
      .then(data => {
        if (data.items) {
          setRecentJobs(data.items);
        }
      })
      .catch(console.error);
  };

  const handleDeleteJob = async (id: string) => {
    if (!confirm('Are you sure you want to delete this job?')) return;
    try {
      const res = await fetch(`/api/v1/jobs/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchRecentJobs();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedJobs.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedJobs.size} jobs?`)) return;
    
    try {
      await Promise.all(Array.from(selectedJobs).map(id => fetch(`/api/v1/jobs/${id}`, { method: 'DELETE' })));
      setSelectedJobs(new Set());
      fetchRecentJobs();
    } catch (err) {
      console.error(err);
    }
  };

  React.useEffect(() => {
    fetchRecentJobs();
  }, []); // Only on mount, we will poll manually or rely on events

  // Poll recent jobs every 3 seconds to update statuses
  useEffect(() => {
    const interval = setInterval(fetchRecentJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const [llmAggressiveness, setLlmAggressiveness] = useState('balanced');
  const [enableLlm, setEnableLlm] = useState(false);

  const updateQueueItem = (id: string, patch: Partial<QueueItem>) => {
    setUploadQueue(prev =>
      prev.map(i => i.id === id ? { ...i, ...patch } : i)
    );
  };

  const removeFromQueue = (id: string) => {
    setUploadQueue(prev => prev.filter(i => i.id !== id));
  };

  const startSequentialUpload = async () => {
    setIsUploading(true);
    const pendingItems = uploadQueue.filter(i => i.status === 'pending');

    for (const item of pendingItems) {
      updateQueueItem(item.id, { status: 'uploading' });

      try {
        const formData = new FormData();
        formData.append('file', item.file);
        
        const options: any = {
          device: 'auto',
          use_vlm_image_reconstruction: true,
        };
        if (enableLlm) {
          options.llm_cleanup_aggressiveness = llmAggressiveness;
        }
        
        formData.append('options', JSON.stringify(options));

        const res = await fetch('/api/v1/jobs', {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          const err = await res.text();
          throw new Error(`HTTP ${res.status}: ${err}`);
        }

        const data = await res.json();
        updateQueueItem(item.id, { status: 'queued', jobId: data.job_id });
      } catch (e: any) {
        updateQueueItem(item.id, { status: 'failed', error: e.message });
      }

      await new Promise(r => setTimeout(r, 100));
      fetchRecentJobs();
    }

    setIsUploading(false);
  };

  const retryItem = async (id: string) => {
    updateQueueItem(id, { status: 'pending', error: undefined });
    setTimeout(() => startSequentialUpload(), 0);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex flex-col items-center justify-center border-dashed border-2">
        <UploadCloud className="w-16 h-16 text-blue-500 mb-4" />
        <h3 className="text-xl font-bold text-gray-800 mb-2">Upload Documents</h3>
        <p className="text-gray-500 mb-6 text-center">Drag & Drop multiple files or click to select.<br/>Support PDF, DOCX, PPTX, PNG, JPG</p>
        
        <input 
          type="file" 
          id="fileInput" 
          multiple
          accept=".pdf,.docx,.pptx,.png,.jpg,.jpeg"
          className="hidden" 
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            if (uploadQueue.length + files.length > 50) {
              alert('队列上限为 50 个文件，请分批上传');
              return;
            }
            const newItems: QueueItem[] = files.map(f => ({
              id: generateId(),
              file: f,
              status: 'pending',
            }));
            setUploadQueue(prev => [...prev, ...newItems]);
            e.target.value = '';
          }} 
        />
        <label 
          htmlFor="fileInput" 
          className="cursor-pointer px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition"
        >
          Select Files
        </label>
      </div>

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <h4 className="font-semibold text-gray-800 mb-4">Conversion Options</h4>
        <div className="space-y-4">
          <label className="flex items-center gap-3">
            <input type="checkbox" checked={enableLlm} onChange={e => setEnableLlm(e.target.checked)} className="w-4 h-4 text-blue-600" />
            <span className="text-gray-700">Enable LLM Smart Cleanup</span>
          </label>
          
          {enableLlm && (
            <div className="ml-7 flex items-center gap-3">
              <span className="text-sm text-gray-600">Aggressiveness:</span>
              <select 
                value={llmAggressiveness} 
                onChange={e => setLlmAggressiveness(e.target.value)}
                className="text-sm border border-gray-300 rounded px-2 py-1 outline-none focus:border-blue-500"
              >
                <option value="conservative">Conservative</option>
                <option value="balanced">Balanced</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {uploadQueue.length > 0 && (
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div className="flex justify-between items-center mb-4">
            <h4 className="font-semibold text-gray-800">Upload Queue ({uploadQueue.length})</h4>
            <button 
              onClick={() => setUploadQueue([])} 
              disabled={isUploading}
              className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50"
            >
              Clear Queue
            </button>
          </div>

          <div className="space-y-2 mb-4 max-h-64 overflow-y-auto pr-2">
            {uploadQueue.map(item => (
              <div key={item.id} className="flex justify-between items-center p-3 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-3">
                  {item.status === 'pending'   && <Clock className="w-4 h-4 text-gray-500" />}
                  {item.status === 'uploading' && <Loader className="w-4 h-4 text-blue-500 animate-spin" />}
                  {item.status === 'queued'    && <CheckCircle className="w-4 h-4 text-green-500" />}
                  {item.status === 'failed'    && <XCircle className="w-4 h-4 text-red-500" />}
                  
                  <div className="flex flex-col">
                    <span className="font-medium text-sm text-gray-800 truncate max-w-[300px]">{item.file.name}</span>
                    <span className="text-xs text-gray-500">{(item.file.size / 1024 / 1024).toFixed(1)} MB</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {item.status === 'failed' && (
                    <span className="text-xs text-red-500 max-w-[200px] truncate">{item.error}</span>
                  )}
                  {item.status === 'pending' && !isUploading && (
                    <button onClick={() => removeFromQueue(item.id)} className="text-xs text-gray-500 hover:text-red-500">Remove</button>
                  )}
                  {item.status === 'failed' && !isUploading && (
                    <button onClick={() => retryItem(item.id)} className="text-xs text-blue-500 hover:text-blue-700">Retry</button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-3">
            <button
              className="px-6 py-2 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition disabled:opacity-50 flex items-center justify-center min-w-[120px]"
              onClick={startSequentialUpload}
              disabled={isUploading || uploadQueue.filter(i => i.status === 'pending').length === 0}
            >
              {isUploading ? <><Loader className="w-4 h-4 mr-2 animate-spin" /> Uploading...</> : 'Start Conversion'}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex justify-between items-center mb-4">
          <h4 className="font-semibold text-gray-800">Job Board</h4>
          {selectedJobs.size > 0 && (
            <button 
              onClick={handleBatchDelete}
              className="px-3 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 shadow-sm text-xs font-semibold rounded-lg transition"
            >
              Delete Selected ({selectedJobs.size})
            </button>
          )}
        </div>
        <div className="space-y-3">
          {recentJobs.length === 0 ? (
            <p className="text-sm text-gray-500">No recent conversions found.</p>
          ) : (
            recentJobs.map(job => (
              <div key={job.id} className="flex justify-between items-center p-3 border rounded-xl bg-gray-50 hover:bg-gray-100 transition">
                <div className="flex items-center gap-3">
                  <input 
                    type="checkbox" 
                    className="w-4 h-4 text-blue-600 rounded border-gray-300"
                    checked={selectedJobs.has(job.id)}
                    onChange={(e) => {
                      const newSet = new Set(selectedJobs);
                      if (e.target.checked) newSet.add(job.id);
                      else newSet.delete(job.id);
                      setSelectedJobs(newSet);
                    }}
                  />
                  <div>
                    <p className="font-medium text-sm text-gray-800 truncate max-w-[200px] sm:max-w-[400px]" title={job.input_filename}>{job.input_filename}</p>
                    <p className="text-xs text-gray-500">{new Date(job.created_at).toLocaleString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded-md text-[10px] font-bold flex items-center gap-1 ${
                    job.status === 'SUCCESS' ? 'bg-green-100 text-green-700' : 
                    job.status === 'FAILED' ? 'bg-red-100 text-red-700' : 
                    'bg-blue-100 text-blue-700'
                  }`}>
                    {job.status === 'RUNNING' || job.status === 'PENDING' ? <Loader className="w-3 h-3 animate-spin" /> : null}
                    {job.status}
                  </span>
                  <div className="flex gap-2">
                    {(job.status === 'SUCCESS' || job.status === 'FAILED') && (
                      <button 
                        onClick={() => onJobComplete && onJobComplete(job.id)}
                        className="px-3 py-1 bg-white border shadow-sm text-xs font-medium rounded-lg hover:bg-gray-50 text-gray-700"
                      >
                        View
                      </button>
                    )}
                    <button 
                      onClick={() => handleDeleteJob(job.id)}
                      className="px-3 py-1 bg-white border shadow-sm text-xs font-medium rounded-lg hover:bg-red-50 text-red-600"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
