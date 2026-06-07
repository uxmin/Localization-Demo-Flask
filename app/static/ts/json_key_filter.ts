import "./utils/tabs.js";

document.getElementById("dwnbtn")?.addEventListener("click", async () => {
  const zipFileInput = document.querySelector('input[name="zip_file"]') as HTMLInputElement | null;
  const removeKeySelect = document.querySelector("select") as HTMLSelectElement | null;

  if (!zipFileInput || !removeKeySelect) {
    alert("요소를 찾을 수 없습니다.");
    return;
  }

  const removeKey = removeKeySelect.value;

  if (!zipFileInput.files || zipFileInput.files.length === 0 || !removeKey) {
    alert("모든 항목을 순서에 따라 입력해주세요.");
    return;
  }

  const data = new FormData();
  data.append("zip_file", zipFileInput.files[0]);
  data.append("remove_key", removeKey);

  try {
    const response = await fetch("/demo/file/remove-keys", {
      method: "POST",
      body: data,
    });

    const contentType = response.headers.get("Content-Type") || "";

    if (response.ok && contentType.includes("application/json")) {
      const jsonResponse = await response.json();
      alert(`파일을 다운로드하는 동안 오류가 발생했습니다. (Error: ${jsonResponse.message})`);
    } else if (response.ok) {
      const originalZipFileName = zipFileInput.files[0].name;
      const fileNameWithoutExtension = originalZipFileName.replace(/\.[^/.]+$/, "");

      const now = new Date();
      const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
      const datePart = localNow.toISOString().slice(2, 10).replace(/-/g, ""); // '241211'
      const timePart = localNow.toISOString().slice(11, 19).replace(/:/g, ""); // '050827'
      const datetimeFormat = `${datePart}-${timePart}`;
      const filename = `${fileNameWithoutExtension}_remove_${removeKey}_${datetimeFormat}.zip`;

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
