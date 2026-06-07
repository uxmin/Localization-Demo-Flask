import { fetchData } from "./utils/api.js";

document.querySelector('input[name="excel_file"]')?.addEventListener("change", (e: Event) => {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  const reader = new FileReader();

  reader.onload = async (e) => {
    const data = new FormData();
    data.append("excel_file", file);

    try {
      const response = await fetchData("/demo/file/extract-columns", data);
      if (response.status_code !== 200) {
        alert(response.error.message);
        window.location.reload();
        return;
      }

      // 초기화
      const selectElement = document.querySelector('section[aria-label="2"] select') as HTMLSelectElement | null;
      if (!selectElement) return;

      selectElement.innerHTML = "";
      selectElement.add(new Option("선택", ""));

      response.data.columns.forEach((header: string) => {
        const optionElement = new Option(header, header);
        selectElement.add(optionElement);
      });
    } catch (error) {
      console.error("Error processing Excel file:", error);
    }
  };
  reader.readAsArrayBuffer(file);
});

document.getElementById("dwnbtn")?.addEventListener("click", async () => {
  const selectElement = document.querySelector("select") as HTMLSelectElement | null;
  const excelFileInput = document.querySelector('input[name="excel_file"]') as HTMLInputElement | null;
  const archiveFileInput = document.querySelector('input[name="archive_file"]') as HTMLInputElement | null;

  if (!selectElement || !excelFileInput || !archiveFileInput) return;

  const header = selectElement.value;
  const excelFile = excelFileInput.files?.[0];
  const archiveFile = archiveFileInput.files?.[0];

  if (!header || !excelFile || !archiveFile) {
    alert("모든 항목을 순서에 따라 입력해주세요.");
    return;
  }

  const data = new FormData();
  data.append("excel_file", excelFile);
  data.append("header", header);
  data.append("archive_file", archiveFile);

  try {
    const response = await fetch("/demo/file/extract-and-download", {
      method: "POST",
      body: data,
    });

    const contentType = response.headers.get("Content-Type") || "";
    if (response.ok && contentType.includes("application/json")) {
      const jsonResponse = await response.json();
      alert(`파일을 다운로드하는 동안 오류가 발생했습니다. (Error: ${jsonResponse.message})`);
    } else if (response.ok) {
      const originalZipFileName = archiveFile.name;
      const fileNameWithoutExtension = originalZipFileName.replace(/\.[^/.]+$/, "");
      const now = new Date();
      const datetimeFormat = now.toISOString().slice(0, 19).replace(/[-T:]/g, "");
      const filename = `${fileNameWithoutExtension}_${datetimeFormat}.zip`;

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } else {
      alert("파일을 다운로드하는 동안 오류가 발생했습니다. 개발팀에게 문의해주세요.");
    }
  } catch (error) {
    console.error("Download failed:", error);
  }
});
