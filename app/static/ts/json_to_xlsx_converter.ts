import "./utils/tabs.js";

const dwnbtn = document.getElementById("dwnbtn") as HTMLButtonElement | null;

dwnbtn?.addEventListener("click", async () => {
  const targetFileInput = document.querySelector('input[name="target_file"]') as HTMLInputElement | null;
  if (!targetFileInput) {
    alert("요소를 찾을 수 없습니다.");
    return;
  }

  const file = targetFileInput.files?.[0];
  if (!file) {
    alert("모든 항목을 순서에 따라 입력해주세요.");
    return;
  }

  const fileName = file.name.toLowerCase();
  const extension = fileName.split(".").pop();

  let endpoint = "";
  if (extension === "xlsx" || extension === "xls") {
    endpoint = "/demo/file/xlsx-to-json";
  } else if (extension === "zip") {
    endpoint = "/demo/file/json-to-xlsx";
  } else {
    alert("지원되지 않는 파일 형식입니다. (xlsx, xls, zip만 지원)");
    return;
  }

  const data = new FormData();
  data.append("target_file", file);

  try {
    dwnbtn.disabled = true;
    dwnbtn.classList.add("opacity-50", "cursor-not-allowed");
    document.body.classList.add("cursor-wait");

    const response = await fetch(endpoint, {
      method: "POST",
      body: data,
    });

    const contentType = response.headers.get("Content-Type") || "";

    if (response.ok && contentType.includes("application/json")) {
      const jsonResponse = await response.json();
      console.error("Error response:", jsonResponse);
      alert(`파일을 다운로드하는 동안 오류가 발생했습니다. (Error: ${jsonResponse.error.message})`);
    } else if (response.ok) {
      const originalZipFileName = file.name;
      const fileNameWithoutExtension = originalZipFileName.replace(/\.[^/.]+$/, "");

      const now = new Date();
      const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
      const datePart = localNow.toISOString().slice(2, 10).replace(/-/g, ""); // '241211'
      const timePart = localNow.toISOString().slice(11, 19).replace(/:/g, ""); // '050827'
      const datetimeFormat = `${datePart}-${timePart}`;
      const resultExt = extension === "zip" ? "xlsx" : "zip";
      const filename = `${fileNameWithoutExtension}_${extension}_to_${resultExt}_${datetimeFormat}.${resultExt}`;

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
  } finally {
    if (dwnbtn) {
      document.body.classList.remove("cursor-wait");
      dwnbtn.disabled = false;
      dwnbtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
});
