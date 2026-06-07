import { fetchData } from "./utils/api.js";
import "./utils/tabs.js";

function checkTaskStatus(taskId: string, polling: any) {
  const progressContainer = document.querySelector('[name="progressBar"]');
  const progressBar = progressContainer ? progressContainer.querySelector("div") : null;

  const progressStatusContainer = document.querySelector('[name="progressStatus"]');
  const statusFields = progressStatusContainer ? progressStatusContainer.querySelectorAll("div") : null;

  fetch(`/demo/file/translate-bulk/${taskId}`)
    .then((response) => response.json())
    .then((data) => {
      console.log("작업 상태:", data);

      const current = data.current || 0;
      const total = data.total || 100;
      const progress = Math.floor((current / total) * 100);

      if (data.state === "PENDING") {
        if (statusFields) {
          statusFields[0].textContent = "Waiting...";
          statusFields[1].textContent = "";
          statusFields[2].textContent = "";
        }
      } else if (data.state === "PROGRESS") {
        if (statusFields) {
          statusFields[0].textContent = "In progress";
          statusFields[1].textContent = "|";
          statusFields[2].textContent = current + " / " + total + " count";
        }
      }

      if (progressBar) {
        progressBar.style.width = progress + "%";
      }

      if (data.state === "SUCCESS" || data.state === "FAILURE") {
        clearInterval(polling);
        console.log("폴링을 중단합니다.");

        if (statusFields) {
          if (data.state === "SUCCESS") statusFields[0].textContent = "Translate Complete!";
          else statusFields[0].textContent = "Translate Failed.";
          statusFields[1].textContent = "";
          statusFields[2].textContent = "";
        }
      }
    })
    .catch((error) => {
      console.error("작업 상태 조회 중 에러", error);
    });
}

document.addEventListener("DOMContentLoaded", () => {});

const chkBtn = document.getElementById("chkbtn");
if (chkBtn) {
  chkBtn.addEventListener("click", async () => {
    const zipFileInput = document.querySelector('input[name="zip_file"]');
    if (!(zipFileInput instanceof HTMLInputElement) || !zipFileInput.files?.length) {
      alert("모든 항목을 순서에 따라 입력해주세요.");
      return;
    }
    const data = new FormData();
    data.append("zip_file", zipFileInput.files[0]);
    try {
      const result = await fetchData("/demo/file/translate-bulk", data);
      console.log("파일 전송 결과:", result);

      const taskId = result.data.task_id;

      // 1초마다 작업 진행 상태를 폴링
      const polling = setInterval(() => {
        checkTaskStatus(taskId, polling);
      }, 1000);
    } catch (error) {
      console.log(error);
    }
  });
}
