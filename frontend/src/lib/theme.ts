/** Token dạng JS — dùng khi 1 lib (VD graph viz) cần giá trị màu/số trực
 * tiếp thay vì class Tailwind. Phải khớp tay với @theme trong src/index.css
 * vì CSS custom property không export sang JS được. */
export const theme = {
  line: "#d6d6d1",
  teal: "#3b9ab8",
  ink: "#111111",
  bgColor: "#f5f5f2",
} as const;
