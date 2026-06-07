import type { ApiResponse, Post } from "./models/interface";

let currentPage: number = 1;
let currentSortField: string = "";
let currentSortDirection: "asc" | "desc" = "desc";
let currentSearch: string = "";

const limit = 10;

async function fetchPosts(page: number = 1): Promise<void> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });

  if (currentSortField) {
    params.set("sort", currentSortField);
    params.set("direction", currentSortDirection);
  }
  if (currentSearch) {
    params.set("search", currentSearch);
  }

  const response = await fetch(`/demo/internal/list?${params.toString()}`);
  if (!response.ok) return;

  const json: ApiResponse = await response.json();
  console.log("json", json);

  if (Array.isArray(json.data)) {
    renderPosts(json.data as Post[]);
  } else {
    console.error("Invalid data format:", json.data);
  }
  renderPagination(json.meta?.page ?? 1, json.meta?.total ?? 0, json.meta?.limit ?? limit);
}

function renderPosts(posts: Post[]): void {
  const tbody = document.getElementById("postTableBody") as HTMLElement;
  tbody.innerHTML = "";

  const statusClassMap: Record<string, { text: string; classes: string }> = {
    pending: {
      text: "Pending",
      classes: "text-gray-600 bg-gray-50 ring-gray-500/10",
    },
    in_progress: {
      text: "In Progress",
      classes: "text-yellow-800 bg-yellow-50 ring-yellow-600/20",
    },
    completed: {
      text: "Completed",
      classes: "text-green-700 bg-green-50 ring-green-600/20",
    },
  };
  posts.forEach((post) => {
    const tr = document.createElement("tr");
    tr.className = "bg-white border-b border-gray-200";

    const status = statusClassMap[post.status] || statusClassMap.pending;

    tr.innerHTML = `
      <th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap">
        ${post.title}
      </th>
      <td class="px-6 py-4">${post.start_date}</td>
      <td class="px-6 py-4">${post.end_date}</td>
      <td class="px-6 py-4">
        <span class="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md ring-1 ring-inset ${status.classes}">
          ${status.text}
        </span>
      </td>
      <td class="px-6 py-4 text-right">
        <a href="/demo/edit/${post.id}" class="font-medium text-blue-600 hover:underline">Edit</a>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderPagination(current: number, total: number, perPage: number): void {
  const container = document.getElementById("paginationContainer") as HTMLElement;
  container.innerHTML = "";

  const totalPages = Math.ceil(total / perPage);
  const maxPagesToShow = 5;

  const createPageItem = (label: string | number, page: number, isActive = false): HTMLLIElement => {
    const li = document.createElement("li");
    li.innerHTML = `
      <a href="#" ${isActive ? 'aria-current="page"' : ""}
         class="flex items-center justify-center h-10 px-4 leading-tight text-sm
                ${
                  isActive
                    ? "text-blue-600 border border-blue-300 bg-blue-50"
                    : "text-gray-500 bg-white border border-gray-300 hover:bg-gray-100 hover:text-gray-700"
                }">
        ${label}
      </a>
    `;
    const anchor = li.querySelector("a") as HTMLAnchorElement;
    anchor.addEventListener("click", (e: MouseEvent) => {
      e.preventDefault();
      if (page !== currentPage) {
        currentPage = page;
        fetchPosts(currentPage);
      }
    });
    return li;
  };

  // 맨 앞으로 버튼 (<<)
  if (current > 1) {
    const li = createPageItem("«", 1);
    container.appendChild(li);
  }

  // 시작 페이지 계산
  let startPage = Math.max(current - Math.floor(maxPagesToShow / 2), 1);
  let endPage = startPage + maxPagesToShow - 1;

  // 마지막 페이지 범위 조정
  if (endPage > totalPages) {
    endPage = totalPages;
    startPage = Math.max(endPage - maxPagesToShow + 1, 1);
  }

  // 페이지 번호 버튼
  for (let i = startPage; i <= endPage; i++) {
    container.appendChild(createPageItem(i, i, i === current));
  }

  // 맨 뒤로 버튼 (>>)
  if (current < totalPages) {
    const li = createPageItem("»", totalPages);
    container.appendChild(li);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  fetchPosts(1);
});

document.querySelectorAll("th a[data-sort]").forEach((a) => {
  a.addEventListener("click", (e: Event) => {
    e.preventDefault();

    const anchor = a as HTMLAnchorElement;
    const sortField = anchor.dataset.sort;
    if (currentSortField === sortField) {
      currentSortDirection = currentSortDirection === "asc" ? "desc" : "asc";
    } else {
      currentSortField = sortField || "";
      currentSortDirection = "asc";
    }

    fetchPosts(1); // 정렬 변경 시 첫 페이지로 리셋
  });
});

document.querySelector("form")?.addEventListener("submit", (e: Event) => {
  e.preventDefault();

  const input = document.getElementById("simple-search") as HTMLInputElement;
  currentSearch = input.value.trim();

  fetchPosts(1); // 검색 시 1페이지로 초기화
});
