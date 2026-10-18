# Frontend

React + Tailwind + Iconify, phong cách neo-brutalism (border + box-shadow,
bo góc 8px). Khung đã dựng xong (chạy được, build được, test pass); các
trang vẫn chỉ hiển thị placeholder vì backend chưa có logic thật — xem
[TODO.md](../TODO.md) ở thư mục gốc.

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
  api/client.ts            Gọi backend qua /api (xem vite.config.ts proxy)
  components/
    ui/                       Card, Button — primitive neo-brutalism
    graph/GraphView.tsx        TODO — hiển thị Knowledge Graph thật
  pages/
    Dashboard.tsx              TODO — chọn domain + chạy benchmark
    BenchmarkResult.tsx         TODO — bảng/biểu đồ so sánh kết quả
  lib/theme.ts              Token neo-brutalism dạng JS (khớp src/index.css)
```

Token neo-brutalism (`--radius-brutal`, `--shadow-brutal`...) định nghĩa ở
`src/index.css` qua Tailwind v4 `@theme`.
