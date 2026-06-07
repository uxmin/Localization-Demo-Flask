import { readdirSync } from "fs";
import { resolve } from "path";
import { defineConfig } from "vite";

// ① app/static/ts 하위의 *.ts 를 자동 스캔해 input 객체 생성
function getEntries() {
  const dir = resolve(__dirname, "app/static/ts");
  const entries: Record<string, string> = {};

  readdirSync(dir, { withFileTypes: true }).forEach((ent) => {
    if (ent.isFile() && ent.name.endsWith(".ts")) {
      const name = ent.name.replace(/\.ts$/, "");
      entries[name] = resolve(dir, ent.name); // { index: ".../index.ts", ... }
    } else if (ent.isDirectory()) {
      // utils/tabs.ts → utils_tabs
      const sub = resolve(dir, ent.name);
      readdirSync(sub).forEach((f) => {
        if (f.endsWith(".ts")) entries[`${ent.name}_${f.replace(/\.ts$/, "")}`] = resolve(sub, f);
      });
    }
  });
  return entries;
}

export default defineConfig({
  root: "app/static/ts", // 소스 루트
  build: {
    outDir: "../js", // ⇒ app/static/js
    emptyOutDir: false, // 기존 JS(직접 작성한 파일) 보존
    target: "es2020",
    rollupOptions: {
      input: getEntries(), // 다중 엔트리 주입
      output: {
        entryFileNames: "[name].js", // 원본 TS 이름 유지
        format: "es",
      },
    },
    sourcemap: true,
  },
});
