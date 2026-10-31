# Frontend

React 19 + Vite + Tailwind 4 + Iconify. Hai trang: **Graph** (vẽ toàn bộ graph của một domain,
upload tài liệu) và **Benchmark** (3 model chạy song song, lịch sử).

## Chạy

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxy /api sang backend :8000
```

## Test, lint, build

```bash
npm run test
npm run lint
npm run build
```

## Cấu trúc

```
src/
  main.tsx, App.tsx
  api/client.ts              Gọi backend qua /api (xem vite.config.ts proxy)
  hooks/
    useDomainGraph.ts          Tải graph của domain (đổi reloadKey để tải lại)
    useDocumentUpload.ts       Gửi file lên, poll job trích xuất tới khi xong
  components/
    graph/                     GraphView (react-force-graph-2d), NodeDetailCard (ảnh + thuộc tính, cả Claim)
    benchmark/                 ModelRow, TraceGraph, status
    layout/, ui/               Navbar, Button, Panel, StatStrip
  pages/
    GraphPage.tsx              Chọn domain, thống kê, nút Upload tài liệu
    BenchmarkPage.tsx          Câu hỏi -> 3 model, tab Lịch sử
```

**Upload tài liệu:** chọn file `.txt` / `.md`; backend trích xuất Entity / Relationship / Claim và
thêm vào domain `vinfast_policy`. Xong thì trang chuyển sang domain đó và tải lại graph. Bấm node
`Claim` để xem trạng thái, ngày, điều kiện và đoạn trích nguồn.
