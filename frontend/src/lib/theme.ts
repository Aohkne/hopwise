/** Token neo-brutalism dạng JS — dùng khi 1 lib (VD graph viz) cần giá trị
 * màu/số trực tiếp thay vì class Tailwind. Phải khớp tay với @theme trong
 * src/index.css vì CSS custom property không export sang JS được. */
export const theme = {
  radius: 8,
  borderColor: "#111111",
  accentColor: "#ff6b4a",
  bgColor: "#fdf6e3",
} as const;
