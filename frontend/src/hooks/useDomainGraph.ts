import { useEffect, useState } from "react";
import { getDomainGraph, type GraphPayload } from "../api/client";

type Loaded = { domain: string; payload: GraphPayload };
type Failed = { domain: string; message: string };

/** Tải toàn bộ graph của 1 domain; đổi `reloadKey` để tải lại (VD sau khi upload tài liệu). Loading suy ra từ state (chưa có dữ liệu
 * của đúng domain đang chọn) nên không cần setState đồng bộ trong effect. */
export function useDomainGraph(domain: string, reloadKey = 0) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState<Failed | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDomainGraph(domain)
      .then((payload) => {
        if (!cancelled) setLoaded({ domain, payload });
      })
      .catch((e: Error) => {
        if (!cancelled) setFailed({ domain, message: e.message });
      });
    return () => {
      cancelled = true;
    };
  }, [domain, reloadKey]);

  return {
    payload: loaded?.domain === domain ? loaded.payload : null,
    error: failed?.domain === domain ? failed.message : null,
  };
}
