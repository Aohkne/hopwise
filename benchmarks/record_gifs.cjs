// Chụp từng khung giao diện benchmark để ghép GIF minh hoạ (gọi từ make_gifs.py).
//
//   NODE_PATH=<thư mục có playwright>/node_modules node benchmarks/record_gifs.cjs \
//     <url frontend> <câu hỏi> <thư mục ra>
//
// Mở tab Benchmark > Lịch sử > lượt chạy có câu hỏi đó. Với mỗi model: chụp tab Status,
// bấm tab "Node đã đi qua", rồi bấm lần lượt từng node từ trên xuống (graph bên trên viền
// node đang chọn). Hàng model xếp dọc (graph trên, danh sách dưới) — vừa 3 cột ngang trong README. Ghi PNG + frames.json (thời lượng từng khung).
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const MODELS = [
  ["jev", "JEV"],
  ["ollama", "OLLAMA · LOCAL"],
  ["nvidia", "NVIDIA · API"],
];
const HOLD = { status: 1800, tab: 1000, node: 900, nodeFast: 450, end: 2000 }; // ms mỗi khung (nodeFast: >15 node)

async function main() {
  const [url, question, outDir] = process.argv.slice(2);
  if (!url || !question || !outDir) throw new Error("cần: <url> <câu hỏi> <thư mục ra>");
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 1500 }, deviceScaleFactor: 2 });
  await page.goto(url);
  await page.getByRole("button", { name: "Benchmark" }).click();
  await page.getByRole("tab", { name: /Lịch sử/ }).click();
  await page.getByRole("button", { name: question, exact: false }).first().click();
  await page.getByText("câu hỏi:").waitFor();
  // Chỉ khi quay: khoá chiều ngang khung model (dòng mô tả node dài làm khung nới từ ~670px
  // lên ~800px khi đổi tab) để mọi khung cùng kích thước. Không sửa gì trong ứng dụng.
  // và nới vùng graph (h-72 = 288px) lên 26rem: graph vài chục node bị nén thì nhãn chồng nhau.
  await page.addStyleTag({ content: `section .grid { grid-template-columns: minmax(0, 1fr) !important; }
    section .grid > div:first-child { height: 26rem !important; }
    /* ẩn nhãn kết quả (tìm ra / không tìm ra / lỗi, đúng / sai) và dòng "ground truth": GIF chỉ minh hoạ
       đường đi, kết quả được mô tả bằng chữ dưới hình trong README */
    section h2 > span > span:nth-of-type(n+2) { display: none !important; }
    section dl > div:nth-child(2) { display: none !important; }` });

  const sectionOf = (title) => page.locator("section", { has: page.locator("h2", { hasText: title }) }).first();
  // cùng chiều cao cho cả 3 GIF (tiêu đề có thể xuống dòng khác nhau giữa các model)
  let height = 0;
  for (const [, title] of MODELS) height = Math.max(height, (await sectionOf(title).boundingBox()).height);
  height = Math.ceil(height);

  const manifest = {};
  for (const [key, title] of MODELS) {
    const section = sectionOf(title);
    await section.evaluate((el) => el.scrollIntoView({ block: "start" }));
    await page.waitForTimeout(2500); // graph force-layout ổn định
    const frames = [];
    const shot = async (hold) => {
      const file = path.join(outDir, `${key}-${String(frames.length).padStart(3, "0")}.png`);
      const box = await section.boundingBox();
      await page.screenshot({ path: file, clip: { x: box.x, y: box.y, width: Math.floor(box.width), height } });
      frames.push({ file, hold });
    };

    await shot(HOLD.status); // tab Status
    await section.getByRole("tab", { name: /Node đã đi qua/ }).click();
    await page.waitForTimeout(400);
    await shot(HOLD.tab);
    const items = section.locator("ol > li");
    const count = await items.count();
    for (let i = 0; i < count; i++) {
      await items.nth(i).click();
      await page.waitForTimeout(450);
      await shot(i === count - 1 ? HOLD.end : count > 15 ? HOLD.nodeFast : HOLD.node);
    }
    manifest[key] = { nodes: count, frames };
    console.log(`${key}: ${count} node, ${frames.length} khung`);
  }
  fs.writeFileSync(path.join(outDir, "frames.json"), JSON.stringify(manifest, null, 2));
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
