import { fetchData } from "./utils/api.js";
import "./utils/tabs.js";

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
      const result = await fetchData("/demo/file/check-validate-json", data);
      const errList = result.data;
      const metaInfo = result.meta;

      const totalCntElement = document.getElementById("totalCnt");
      if (totalCntElement) {
        totalCntElement.textContent = metaInfo.totalCnt;
      }
      const jsonCntElement = document.getElementById("jsonCnt");
      if (jsonCntElement) {
        jsonCntElement.textContent = metaInfo.jsonCnt;
      }
      const successCntElement = document.getElementById("successCnt");
      if (successCntElement) {
        successCntElement.textContent = metaInfo.successCnt;
      }
      const failCntElement = document.getElementById("failCnt");
      if (failCntElement) {
        failCntElement.textContent = metaInfo.failCnt;
      }
      const failListElement = document.getElementById("failList");
      if (failListElement) {
        (failListElement as HTMLTextAreaElement).value = errList.join("\n");
      }
    } catch (error) {
      console.log(error);
    }
  });
}
