document.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("/demo/external/models", {
    method: "GET",
  });
  const responseJsonObject = await response.json();
  if (responseJsonObject.status_code !== 200) {
    alert("error!");
    return;
  }

  const models = responseJsonObject.data.models;
  const selectElement = document.querySelector("select") as HTMLSelectElement;
  models.forEach((model: string) => {
    const option = document.createElement("option");
    option.value = model; // value 속성 설정
    option.textContent = model; // 사용자에게 보여지는 텍스트
    selectElement.appendChild(option);
  });
});

document.getElementById("resultBtn")?.addEventListener("click", async (e: MouseEvent) => {
  const modelSelect = document.querySelector("select") as HTMLSelectElement;
  const apiKeyInput = document.getElementById("apiKeyInput") as HTMLInputElement;
  const systemPromptInput = document.getElementById("systemPromptInput") as HTMLTextAreaElement;
  const userPromptInput = document.getElementById("userPromptInput") as HTMLTextAreaElement;

  const agentPromptInput = document.getElementById("agentResponse") as HTMLTextAreaElement;

  if (!apiKeyInput || !userPromptInput) return;
  if (!apiKeyInput.value.trim() || !userPromptInput.value.trim() || !modelSelect.value.trim()) {
    alert("모든 항목을 순서에 따라 입력해주세요.");
    return;
  }

  let systemPrompt = "";
  if (systemPromptInput.value.trim()) {
    systemPrompt = systemPromptInput.value;
  }

  const payload = {
    api_key: apiKeyInput.value,
    system_prompt: systemPrompt,
    user_prompt: userPromptInput.value,
    model_name: modelSelect.value,
  };

  const target = e.target as HTMLButtonElement;
  try {
    target.disabled = true;
    target.classList.add("opacity-50", "cursor-not-allowed");
    document.body.classList.add("cursor-wait");

    const response = await fetch("/demo/external/call-llm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const responseJsonObject = await response.json();
    if (responseJsonObject.status_code !== 200) {
      console.log(responseJsonObject);
      alert(`[${responseJsonObject.error.code}] ${responseJsonObject.error.message}`);
      return;
    }

    const agentResponse = responseJsonObject.data.response;
    agentPromptInput.value = agentResponse;
  } catch (error) {
    console.error("API failed:", error);
  } finally {
    document.body.classList.remove("cursor-wait");
    target.disabled = false;
    target.classList.remove("opacity-50", "cursor-not-allowed");
  }
});
