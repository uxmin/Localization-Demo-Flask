import "./utils/tabs.js";

const sortJsonKeys = (jsonObject: Record<string, any>) => {
  return Object.keys(jsonObject)
    .sort()
    .reduce((sortedObj: Record<string, any>, key) => {
      if (typeof jsonObject[key] === "object" && !Array.isArray(jsonObject[key]) && jsonObject[key] !== null) {
        sortedObj[key] = sortJsonKeys(jsonObject[key]);
      } else {
        sortedObj[key] = jsonObject[key];
      }
      return sortedObj;
    }, {} as Record<string, any>);
};
document.addEventListener("DOMContentLoaded", () => {
  const jsonInput = document.getElementById("jsonInput") as HTMLInputElement | null;
  const jsonViewer = document.getElementById("jsonViewer") as HTMLElement & { data: any };

  if (!jsonInput || !jsonViewer) return;

  // JSON 뷰어를 업데이트하는 함수
  const updateJsonViewer = () => {
    try {
      const inputValue = jsonInput.value.trim();

      if (inputValue) {
        const parsedJson = JSON.parse(inputValue);
        jsonViewer.data = parsedJson;
        jsonViewer.setAttribute("data-json", JSON.stringify(parsedJson));
        jsonViewer.setAttribute("data-is-valid", "true");
      } else {
        jsonViewer.setAttribute("data-json", "{}");
        jsonViewer.data = {};
      }
    } catch (e) {
      const errorData = JSON.stringify({ error: "Invalid JSON input" });
      jsonViewer.setAttribute("data-json", errorData);
      jsonViewer.data = { error: "Invalid JSON input" };
      jsonViewer.setAttribute("data-is-valid", "false");
    }
  };

  jsonInput.addEventListener("input", updateJsonViewer);
  jsonViewer.data = {};
});

document.getElementById("resultBtn")?.addEventListener("click", async (e: MouseEvent) => {
  const jsonInput = document.getElementById("jsonInput") as HTMLInputElement | null;
  const jsonViewer = document.getElementById("jsonViewer") as HTMLElement | null;

  if (!jsonInput || !jsonViewer) return;

  const isValidJson = jsonViewer.getAttribute("data-is-valid") === "true";
  const dataJsonString = jsonViewer.getAttribute("data-json");

  if (!dataJsonString) {
    alert("데이터가 입력되지 않았습니다. 데이터를 입력해주세요.");
    jsonInput.focus();
    return;
  }

  if (!isValidJson) {
    alert("잘못된 JSON 형식입니다. 다시 확인해주세요.");
    jsonInput.focus();
    return;
  }

  const data = JSON.parse(dataJsonString);
  const target = e.target as HTMLButtonElement;
  try {
    target.disabled = true;
    target.classList.add("opacity-50", "cursor-not-allowed");
    document.body.classList.add("cursor-wait");

    const response = await fetch("/demo/external/openai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || "서버에서 알 수 없는 오류가 발생했습니다.");
    }

    const sortedKeys = Object.keys(data);
    const jsonResultJsonData: Record<string, any> = {};

    sortedKeys.forEach((key) => {
      if (key in result.data.translation) {
        jsonResultJsonData[key] = result.data.translation[key];
      }
    });

    const jsonResult = document.getElementById("jsonResult") as HTMLElement & { data: any };
    if (jsonResult) {
      jsonResult.data = jsonResultJsonData;
    }

    const analyze = document.getElementById("analyze") as HTMLElement | null;
    if (analyze) {
      analyze.textContent = result.data.analyze;
    }
  } catch (err: any) {
    console.error(err);
    alert(err.message || "데이터 전송 중 오류가 발생했습니다.");
  } finally {
    document.body.classList.remove("cursor-wait");
    target.disabled = false;
    target.classList.remove("opacity-50", "cursor-not-allowed");
  }
});
