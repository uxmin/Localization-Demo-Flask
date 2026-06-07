"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const pannel = document.querySelector('div[name="pannel"]') || null;
    if (!pannel)
        return;
    const tabs = pannel.querySelectorAll("li");
    const contents = pannel.querySelectorAll('div[name="result"], div[name="log"]');
    tabs.forEach((tab) => {
        tab.addEventListener("click", function () {
            const target = this.getAttribute("data-target");
            if (!target)
                return;
            contents.forEach((content) => {
                const nameAttr = content.getAttribute("name");
                if (nameAttr === target) {
                    content.removeAttribute("hidden");
                }
                else {
                    content.setAttribute("hidden", "true");
                }
            });
            tabs.forEach((t) => {
                const tabEl = t;
                if (tabEl === this) {
                    tabEl.classList.add("border-t-sky-500");
                    tabEl.classList.remove("hover:border-t-sky-200", "cursor-pointer");
                }
                else {
                    tabEl.classList.remove("border-t-sky-500");
                    tabEl.classList.add("hover:border-t-sky-200", "cursor-pointer");
                }
            });
        });
    });
});
