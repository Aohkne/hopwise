import { useEffect, useState } from "react";
import { getDocumentJob, uploadDocument, type DocumentJob } from "../api/client";

const POLL_MS = 1500;

/** Gửi 1 file văn bản lên backend rồi poll job trích xuất tới khi xong. `onDone` gọi đúng một lần
 * khi job thành công (truyền hàm ổn định, VD bọc `useCallback`). */
export function useDocumentUpload(domain: string, onDone: (job: DocumentJob) => void) {
  const [job, setJob] = useState<DocumentJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const timer = setInterval(() => {
      getDocumentJob(job.id)
        .then((next) => {
          setJob(next);
          if (next.status === "error") setError(next.error ?? "Trích xuất thất bại");
          if (next.status === "done") onDone(next);
        })
        .catch((e: Error) => {
          setError(e.message);
          setJob({ ...job, status: "error", error: e.message });
        });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [job, onDone]);

  async function upload(file: File) {
    setError(null);
    setStarting(true);
    try {
      setJob(await uploadDocument(file.name, await file.text(), domain));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  return { job, error, busy: starting || job?.status === "running", upload };
}
