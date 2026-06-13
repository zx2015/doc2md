| Version | Date       | Description                                | Author     |
| :------ | :--------- | :----------------------------------------- | :--------- |
| v1.0.0  | 2026-06-13 | Initial design for Job History UI and API  | Gemini CLI |

# UI History & Job Tracking Design

## 1. Requirement Overview
Users currently lose access to processed files (both raw markdown and rendered views) once they upload a new file or navigate away from the current preview session. We need a "Recent Jobs" or "History" list on the Dashboard to allow users to view, download, or re-access previously processed jobs.

## 2. API Design

### 2.1 Fetch Job History (`GET /api/v1/jobs`)
The existing endpoint `GET /api/v1/jobs` already supports basic pagination and listing. 
**Endpoint**: `GET /api/v1/jobs?page=1&limit=10`
**Response**:
```json
{
  "total": 15,
  "items": [
    {
      "id": "uuid",
      "status": "SUCCESS",
      "input_filename": "test.pdf",
      "created_at": "2026-06-13T10:00:00Z"
    }
  ]
}
```

## 3. Frontend UI Design

### 3.1 Component Architecture
1. **RecentJobs component**: A new component `src/features/dashboard/RecentJobs.tsx` or inline in `Dashboard.tsx` depending on complexity.
2. **Location**: Displayed at the bottom of the `Dashboard` layout, below the upload form.
3. **Data Fetching**: 
   - `useEffect` hook to poll or fetch `/api/v1/jobs?limit=5` on component mount or when a new job succeeds.
4. **Interactions**:
   - Each row displays: `input_filename`, `status`, `created_at`.
   - "View" button: Sets the global `completedJobId` to trigger the `Preview` component mount.

## 4. Implementation Steps
1. Create frontend API fetching logic for `GET /api/v1/jobs`.
2. Add the `Recent Jobs` UI section in `Dashboard.tsx`.
3. Wire the "View" action to pass the `jobId` to the `App` state (so `Preview.tsx` takes over).

---

## Related
- [Architecture Overview](ARCH_OVERVIEW.md)
- [Requirements Index](../requirements/index.md)
