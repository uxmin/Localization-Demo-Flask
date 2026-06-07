import Swal from "sweetalert2";

const addBtn = document.getElementById("addbtn");
if (addBtn) {
  addBtn.addEventListener("click", async () => {
    const { value: storeName } = await Swal.fire({
      title: "Let's add!",
      input: "text",
      inputLabel: "식당 이름이 무엇인가요?",
      inputPlaceholder: "예) 맛있는 식당",
      showCancelButton: true,
      inputValidator: (value) => {
        if (!value) {
          return "식당 이름을 입력해주세요.";
        }
      },
    });
    if (storeName) {
      const { value: storeUrl } = await Swal.fire({
        title: "Let's add!",
        input: "url",
        html: "식당 위치 링크를 공유해주세요.",
        inputPlaceholder: "https://example.com/restaurant",
        showCancelButton: true,
        inputValidator: (value) => {
          const urlPattern = new RegExp(
            "^(https?:\\/\\/)?" + // 프로토콜
              "((([a-zA-Z\\d]([a-zA-Z\\d-]*[a-zA-Z\\d])*)\\.?)+[a-zA-Z]{2,}|" + // 도메인 이름
              "((\\d{1,3}\\.){3}\\d{1,3}))" + // IPv4 주소
              "(\\:\\d+)?(\\/[-a-zA-Z\\d%_.~+]*)*" + // 포트와 경로
              "(\\?[;&a-zA-Z\\d%_.~+=-]*)?" + // 쿼리 문자열
              "(\\#[-a-zA-Z\\d_]*)?$", // 프래그먼트 로케이터
            "i"
          );
          if (!value) {
            return "위치를 정확하게 입력해주세요.";
          } else if (!urlPattern.test(value)) {
            return "유효한 URL을 입력해주세요.";
          }
        },
      });

      if (storeUrl) {
        const { value: description } = await Swal.fire({
          input: "textarea",
          inputLabel: "식당에 대해서 간단하게 알려주세요.",
          inputPlaceholder: "예) 가성비 좋은 점심 맛집",
          showCancelButton: true,
          inputValidator: (value) => {
            if (!value) {
              return "식당에 대한 설명을 남겨주세요.";
            }
            if (value.length > 100) {
              return "설명은 100자 이내로 입력해주세요.";
            }
          },
        });
        if (description) {
          try {
            const response = await fetch("/demo/common/restaurant", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: storeName,
                link: storeUrl,
                description: description,
              }),
            });
            const text = await response.text();
            const data = JSON.parse(text);

            let content = "";
            if (data.status_code === 200) content = "성공적으로 저장되었습니다.";
            Swal.fire({
              text: content ? content : data.error.message,
            }).then(() => window.location.reload());
          } catch (err) {
            console.error(err);
          }
        }
      }
    }
  });
}

function openLinkInNewTab(divElement: HTMLElement) {
  const parentElement = divElement.parentElement;
  if (!parentElement) return;

  const link = parentElement.querySelector("a.hidden-link") as HTMLAnchorElement | null;
  if (!link || !link.href) return;

  window.open(link.href, "_blank");
}

function deleteRestaurant(button: HTMLButtonElement) {
  const div = button.closest("div");
  if (!div) return;

  const h1 = div.querySelector("h1");
  if (!h1) return;

  const name = h1.innerText;

  Swal.fire({
    icon: "warning",
    text: "정말로 삭제하시겠어요? 삭제 후에는 복구할 수 없습니다.",
    showCancelButton: true,
  }).then((data) => {
    if (data.isConfirmed) {
      fetch("/demo/common/restaurant", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name }),
      })
        .then((response) => response.json())
        .then((data) => {
          let content = "";
          if (data.status_code === 200) content = "성공적으로 삭제되었습니다.";
          Swal.fire({
            text: content ? content : data.error.message,
          }).then(() => window.location.reload());
        });
    }
  });
}

declare global {
  interface Window {
    openLinkInNewTab: (divElement: HTMLElement) => void;
    deleteRestaurant: (button: HTMLButtonElement) => void;
  }
}
window.openLinkInNewTab = openLinkInNewTab;
window.deleteRestaurant = deleteRestaurant;
