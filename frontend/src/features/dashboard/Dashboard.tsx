import React, { useState } from 'react';
import useWebSocket from 'react-use-websocket';
import { UploadCloud, FileText, CheckCircle, AlertCircle } from 'lucide-react';

export default function Dashboard({ onJobComplete }: { onJobComplete?: (jobId: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [message, setMessage] = useState<string>('');
  const [stage, setStage] = useState<string>('');
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());

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
  }, [status]);

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const { lastJsonMessage } = useWebSocket(
    jobId ? `${wsProtocol}//${window.location.host}/api/v1/ws/jobs/${jobId}` : null,
    {
      onOpen: () => console.log('WS connected'),
      shouldReconnect: () => true,
    }
  );

  React.useEffect(() => {
    if (lastJsonMessage) {
      const data = lastJsonMessage as any;
      if (data.type === 'snapshot' || data.type === 'progress') {
        setProgress(data.percent || 0);
        setMessage(data.message || '');
        setStage(data.stage || '');
        setStatus('RUNNING');
      } else if (data.type === 'completed') {
        setStatus('SUCCESS');
        setProgress(100);
        setMessage('Conversion complete!');
        if (onJobComplete) onJobComplete(data.job_id);
      } else if (data.type === 'failed') {
        setStatus('FAILED');
        setMessage(data.error || 'Failed');
      }
    }
  }, [lastJsonMessage, onJobComplete]);

  const [useVlm, setUseVlm] = useState(false);


  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('options', JSON.stringify({ 
      device: 'auto',
      use_vlm_image_reconstruction: useVlm
    }));

    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setJobId(data.job_id);
        setStatus('PENDING');
        setProgress(0);
        setMessage('Job accepted, waiting for worker...');
      } else {
        alert("Upload failed: " + data.detail);
      }
    } catch (err) {
      console.error(err);
      alert("Network error");
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex flex-col items-center justify-center border-dashed border-2">
        <UploadCloud className="w-16 h-16 text-blue-500 mb-4" />
        <h3 className="text-xl font-bold text-gray-800 mb-2">Upload Document</h3>
        <p className="text-gray-500 mb-6 text-center">Support PDF, DOCX, PPTX and Images</p>
        
        <input 
          type="file" 
          id="fileInput" 
          className="hidden" 
          onChange={(e) => setFile(e.target.files?.[0] || null)} 
        />
        <label 
          htmlFor="fileInput" 
          className="cursor-pointer px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition"
        >
          Select File
        </label>
        {file && <div className="mt-4 text-sm text-gray-600 flex items-center gap-2"><FileText className="w-4 h-4"/> {file.name}</div>}
      </div>

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <h4 className="font-semibold text-gray-800 mb-4">Conversion Options</h4>
        <div className="space-y-3">
          <label className="flex items-center gap-3">
            <input type="checkbox" checked={useVlm} onChange={e => setUseVlm(e.target.checked)} className="w-4 h-4 text-blue-600" />
            <span className="text-gray-700">Enable VLM Image Reconstruction (Requires Vision Model)</span>
          </label>
        </div>
      </div>

      {file && !jobId && (
        <button 
          onClick={handleUpload}
          className="w-full py-4 bg-gray-900 text-white rounded-xl font-semibold hover:bg-gray-800 transition"
        >
          Start Conversion
        </button>
      )}

      {jobId && (
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div className="flex justify-between items-center mb-4">
            <h4 className="font-semibold text-gray-800">Job: {jobId.split('-')[0]}...</h4>
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${status === 'SUCCESS' ? 'bg-green-100 text-green-700' : status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
              {status}
            </span>
          </div>
          
          <div className="w-full bg-gray-100 rounded-full h-3 mb-4 overflow-hidden">
            <div 
              className={`h-3 rounded-full transition-all duration-500 ${status === 'FAILED' ? 'bg-red-500' : 'bg-blue-500'}`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          
          <div className="flex items-center gap-2 text-sm text-gray-600">
            {status === 'SUCCESS' && <CheckCircle className="w-4 h-4 text-green-500" />}
            {status === 'FAILED' && <AlertCircle className="w-4 h-4 text-red-500" />}
            {status === 'RUNNING' && stage === 'vlm_image' ? (
              <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            ) : status === 'RUNNING' && (
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            )}
            <p className={stage === 'vlm_image' ? "text-purple-600 font-medium" : ""}>{message || 'Initializing...'}</p>
          </div>
          {(status === 'SUCCESS' || status === 'FAILED') && (
            <button 
              onClick={() => { setJobId(null); setFile(null); setStatus(''); setProgress(0); setMessage(''); }}
              className="mt-4 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition text-sm font-medium"
            >
              Upload Another
            </button>
          )}
        </div>
      )}

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex justify-between items-center mb-4">
          <h4 className="font-semibold text-gray-800">Recent Conversions</h4>
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
                  <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${job.status === 'SUCCESS' ? 'bg-green-100 text-green-700' : job.status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
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
