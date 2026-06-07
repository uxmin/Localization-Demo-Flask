import "./utils/tabs.js";

declare var Choices: any;
let choicesInstance: any = null;

document.addEventListener("DOMContentLoaded", () => {
  const originFileInput = document.querySelector('input[name="origin_file"]') as HTMLInputElement;
  const selectBox = document.querySelector('section[aria-label="3"] select') as HTMLSelectElement;
  const tbody = document.querySelector("tbody") as HTMLTableSectionElement;

  originFileInput.addEventListener("change", async (event: Event) => {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file || !file.name.endsWith(".zip")) return;

    const data = new FormData();
    data.append("origin_file", file);
    try {
      const response = await fetch("/demo/file/get-keys-zip-file", {
        method: "POST",
        body: data,
      });
      if (response.ok) {
        const jsonResponse = await response.json();
        // console.log("jsonResponse", jsonResponse);

        if (jsonResponse.status_code !== 200) {
          alert(
            "추출이 가능한 형식이 아닙니다. (original, localized)\n형식을 다시 확인해주세요.\n\n에러가 계속되면 개발팀에게 문의해주세요."
          );
          return;
        }

        const keys: string[] = jsonResponse.data?.keys || [];

        // 기존 Choices 인스턴스 제거 (중복 방지)
        if (choicesInstance) {
          choicesInstance.destroy();
          selectBox.innerHTML = ""; // Choices에서 추가한 UI까지 제거
        }

        // select 내부 비우고 새 option 설정
        selectBox.innerHTML = "";
        keys.forEach((key) => {
          const option = document.createElement("option");
          option.value = key;
          option.textContent = key;
          selectBox.appendChild(option);
        });

        // 자동 선택 방지
        selectBox.selectedIndex = -1;
        selectBox.multiple = true;

        choicesInstance = new Choices(selectBox, {
          removeItemButton: true,
          placeholder: true,
          maxItemCount: 10,
          shouldSort: true,
          addChoices: true,
          addItems: true,
        });
      } else {
        alert("오류가 발생했습니다. 개발팀에게 문의해주세요.");
      }
    } catch (error) {
      console.error("Error uploading file:", error);
    }
  });

  selectBox.addEventListener("change", () => {
    const selectedValues = Array.from(selectBox.selectedOptions).map((opt) => opt.value);

    Array.from(tbody.querySelectorAll("tr")).forEach((row) => {
      const id = row.querySelector("td:last-child")?.id;
      if (id && id !== "etc" && id !== "totalCnt") {
        row.remove();
      }
    });

    const etcRow = document.getElementById("etc")?.closest("tr");
    if (!etcRow) return;

    selectedValues.forEach((value) => {
      const tr = document.createElement("tr");
      tr.className = "border-b";

      const tdKey = document.createElement("td");
      tdKey.className = "px-2";
      tdKey.textContent = value;

      const tdVal = document.createElement("td");
      tdVal.className = "px-2 text-right";
      tdVal.id = value;
      tdVal.textContent = "0";

      tr.appendChild(tdKey);
      tr.appendChild(tdVal);
      tbody.insertBefore(tr, etcRow);
    });
  });
});

document.getElementById("actionBtn")?.addEventListener("click", async () => {
  const checkbox = document.getElementById("downloadCheckbox") as HTMLInputElement;
  const originFileInput = document.querySelector('input[name="origin_file"]') as HTMLInputElement;
  const workFileInput = document.querySelector('input[name="work_file"]') as HTMLInputElement;
  const selectBox = document.querySelector('section[aria-label="3"] select') as HTMLSelectElement;

  if (!originFileInput.files?.length || !workFileInput.files?.length || !selectBox.value) {
    alert("모든 항목을 순서에 따라 입력해주세요.");
    return;
  }

  const data = new FormData();
  data.append("origin_file", originFileInput.files[0]);
  data.append("work_file", workFileInput.files[0]);
  data.append("selected_keys", JSON.stringify(Array.from(selectBox.selectedOptions).map((opt) => opt.value)));

  try {
    const response = await fetch("/demo/file/apply-changes-and-download", {
      method: "POST",
      body: data,
    });

    const contentType = response.headers.get("Content-Type") || "";
    if (response.ok && contentType.includes("application/json")) {
      const jsonResponse = await response.json();
      alert(`파일을 다운로드하는 동안 오류가 발생했습니다. (Error: ${jsonResponse.error.message})`);
    } else if (response.ok) {
      const metadataRaw = response.headers.get("X-Metadata");
      const metadataObj: Record<string, any> = JSON.parse(metadataRaw?.replace(/'/g, '"') || "{}");

      const errList: string[] = metadataObj.err_list || [];
      // console.log("errList", errList);

      const originalZipFileName = originFileInput.files[0].name;
      const fileName = originalZipFileName.replace(/\.[^/.]+$/, "");

      const now = new Date();
      const yymmdd = now.toISOString().slice(2, 10).replace(/-/g, "");
      const filename = `${fileName}_${yymmdd}_output.zip`;

      if (checkbox?.checked) {
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
      }

      let editTotalCnt = 0;

      Object.entries(metadataObj).forEach(([key, value]) => {
        if (["zip_path", "err_list", "total_cnt"].includes(key)) return;
        const element = document.getElementById(key);
        if (element) {
          element.textContent = value;
          editTotalCnt += parseInt(value) || 0;
        }
      });
      (document.getElementById("totalCnt") as HTMLElement).textContent = String(editTotalCnt);
      (document.getElementById("total") as HTMLElement).textContent = metadataObj.total_cnt;
      (document.getElementById("success") as HTMLElement).textContent = String(
        parseInt(metadataObj.total_cnt, 10) - errList.length
      );
      (document.getElementById("fail") as HTMLElement).textContent = String(errList.length);
      (document.getElementById("failList") as HTMLTextAreaElement).value = errList.join("\n");
    } else {
      alert("파일을 다운로드하는 동안 오류가 발생했습니다. 개발팀에게 문의해주세요.");
    }
  } catch (error) {
    console.error("Download failed:", error);
  }
});
