import Swal from "sweetalert2";
import "./utils/tabs.js";

const API_ENDPOINTS = {
  LOOKUP_REPO: "/demo/external/lookup-repo",
  DOWNLOAD_XLSX: "/demo/external/download-xlsx",
  DOWNLOAD_WORKFILE: "/demo/external/download-workfile",
  UPLOAD_WORKFILE: "/demo/external/upload-workfile",
  DOWNLOAD_KPI: "/demo/external/download-kpi",
  S3_UPLOAD_FROM_COMMITS: "/demo/external/s3-upload-from-commits",
};

interface Commit {
  message: string;
  author: string;
  committed_at: string;
}

interface RepoData {
  items: string[];
  task_done: number;
  review_done: number;
  total_done: number;
  total: number;
  commits: Commit[];
}

interface RepoInfo {
  repo_url: string;
  branch: string;
  path: string;
}

/**
 * 사용자에게 알림을 보여주는 서비스
 */
const NotificationService = {
  success(title: string, text: string) {
    return Swal.fire(title, text, "success");
  },
  error(title: string, text: string) {
    return Swal.fire(title, text, "error");
  },
  confirm(title: string, text: string) {
    return Swal.fire({
      title,
      text,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Yes",
      cancelButtonText: "No",
    });
  },
  alert(message: string) {
    // 기존 alert를 Swal로 대체하여 일관성 유지
    Swal.fire("알림", message, "info");
  },
};

/**
 * DOM 관련 헬퍼 함수
 */
const DOMHelper = {
  /**
   * 요소의 로딩 상태를 설정/해제하고 커서를 변경합니다.
   * @param element - 상태를 변경할 HTML 요소
   * @param isLoading - 로딩 상태 여부
   */
  setLoadingState(element: HTMLElement | null, isLoading: boolean) {
    if (element) {
      if (element instanceof HTMLButtonElement) {
        element.disabled = isLoading;
      }
      element.classList.toggle("opacity-50", isLoading);
      element.classList.toggle("cursor-not-allowed", isLoading);
    }
    document.body.classList.toggle("cursor-wait", isLoading);
  },

  /**
   * Fetch API 응답으로부터 파일을 다운로드합니다.
   * @param response - Fetch 응답 객체
   * @param defaultFilename - 기본 파일명
   */
  async downloadFileFromResponse(response: Response, defaultFilename: string = "download.zip") {
    const disposition = response.headers.get("Content-Disposition");
    let filename = defaultFilename;

    if (disposition && disposition.includes("filename=")) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match?.[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

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
  },
};

class RepoPageManager {
  // DOM 요소 참조
  private repoUrlInput!: HTMLInputElement;
  private branchInput!: HTMLInputElement;
  private pathInput!: HTMLInputElement;
  private chkRepoButton!: HTMLButtonElement;
  private reloadButton!: HTMLButtonElement;
  private dwnXlsxButton!: HTMLButtonElement;
  private dwnWorkListButton!: HTMLButtonElement;
  private dwnKPIButton!: HTMLButtonElement;
  private s3UploadButton!: HTMLButtonElement;
  private dropzoneLabel!: HTMLLabelElement;
  private fileInput!: HTMLInputElement;

  // 섹션 요소들
  private chkRepoSection!: HTMLElement;
  private dataFoundDiv!: HTMLElement;
  private uploadFormDiv!: HTMLElement;
  private dataText!: HTMLElement;
  private commitsContainer!: HTMLElement;
  private completedText!: HTMLElement;
  private progressBar!: HTMLElement;
  private workedText!: HTMLElement;
  private reviewedText!: HTMLElement;

  constructor() {
    this.queryDOMElements();
    this.setupEventListeners();
  }

  /**
   * 필요한 모든 DOM 요소를 한 번에 찾아 속성에 할당합니다.
   */
  private queryDOMElements() {
    const getElement = <T extends HTMLElement>(id: string): T => {
      const el = document.getElementById(id);
      if (!el) throw new Error(`Element with id "${id}" not found.`);
      return el as T;
    };

    this.repoUrlInput = getElement<HTMLInputElement>("repo_url");
    this.branchInput = getElement<HTMLInputElement>("branch");
    this.pathInput = getElement<HTMLInputElement>("path");

    this.chkRepoButton = getElement<HTMLButtonElement>("chkRepo");
    this.reloadButton = getElement<HTMLButtonElement>("reload");
    this.dwnXlsxButton = getElement<HTMLButtonElement>("dwnXlsx");
    this.dwnWorkListButton = getElement<HTMLButtonElement>("dwnWorkList");
    this.dwnKPIButton = getElement<HTMLButtonElement>("dwnKPI");
    this.s3UploadButton = getElement<HTMLButtonElement>("dwnbtn");

    this.dropzoneLabel = document.querySelector('label[for="dropzone-file"]') as HTMLLabelElement;
    this.fileInput = getElement<HTMLInputElement>("dropzone-file");

    this.chkRepoSection = getElement("chkRepoSection");
    this.dataFoundDiv = this.chkRepoSection.querySelector(".data-found") as HTMLElement;
    this.uploadFormDiv = this.chkRepoSection.querySelector(".upload-form") as HTMLElement;
    this.dataText = this.chkRepoSection.querySelector(".data-text") as HTMLElement;

    this.commitsContainer = getElement("commits-section");
    this.completedText = getElement("progress-completed-text");
    this.progressBar = getElement("progress-bar");
    this.workedText = getElement("progress-worked");
    this.reviewedText = getElement("progress-reviewed");

    if (!this.dropzoneLabel || !this.dataFoundDiv || !this.uploadFormDiv || !this.dataText) {
      throw new Error("One or more required child elements are missing.");
    }
  }

  /**
   * 모든 이벤트 리스너를 설정합니다.
   */
  private setupEventListeners() {
    this.chkRepoButton?.addEventListener("click", (e) => this.handleLookupRepo(e.target as HTMLButtonElement));
    this.reloadButton?.addEventListener("click", (e) => this.handleReloadCommits(e.target as HTMLButtonElement));
    this.dwnXlsxButton?.addEventListener("click", (e) => this.handleDownloadXlsx(e.target as HTMLButtonElement));
    this.dwnWorkListButton?.addEventListener("click", (e) =>
      this.handleDownloadWorkList(e.target as HTMLButtonElement)
    );
    this.dwnKPIButton?.addEventListener("click", (e) => this.handleDownloadKpi(e.target as HTMLButtonElement));
    this.s3UploadButton?.addEventListener("click", (e) => this.handleS3Upload(e.target as HTMLButtonElement));

    // 파일 업로드 핸들러 설정
    this.fileInput.addEventListener("change", (e) => {
      const target = e.target as HTMLInputElement;
      if (target.files && target.files.length > 0) {
        this.handleUploadWorkFile(target.files[0]);
      }
    });

    this.dropzoneLabel.addEventListener("dragover", this.handleDragOver);
    this.dropzoneLabel.addEventListener("dragleave", this.handleDragLeave);
    this.dropzoneLabel.addEventListener("drop", this.handleDrop);
  }

  /**
   * 입력된 레포지토리 정보를 가져와 유효성을 검사합니다.
   * @returns {RepoInfo}
   */
  private getRepoInfo(shouldFillFromPlaceholder: boolean = false): RepoInfo {
    if (shouldFillFromPlaceholder) {
      [this.repoUrlInput, this.branchInput, this.pathInput].forEach((el) => {
        if (el.value.trim() === "" && el.placeholder) {
          el.value = el.placeholder;
        }
      });
    }

    const repoInfo: RepoInfo = {
      repo_url: this.repoUrlInput.value.trim(),
      branch: this.branchInput.value.trim(),
      path: this.pathInput.value.trim(),
    };

    if (!repoInfo.repo_url || !repoInfo.branch || !repoInfo.path) {
      this.repoUrlInput.focus();
      throw new Error("데이터가 입력되지 않았습니다. 데이터를 입력해주세요.");
    }
    return repoInfo;
  }

  /**
   * API 호출을 감싸는 래퍼 함수
   * @param url - API 엔드포인트
   * @param options - Fetch 옵션
   * @param triggerElement - 로딩 상태를 표시할 요소
   */
  private async apiRequest<T>(url: string, options: RequestInit, triggerElement: HTMLElement | null): Promise<T> {
    DOMHelper.setLoadingState(triggerElement, true);
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errorResult = await response
          .json()
          .catch(() => ({ message: "서버에서 알 수 없는 오류가 발생했습니다." }));
        throw new Error(errorResult.message || "API 요청 실패");
      }
      // JSON 응답이 예상되는 경우
      if (response.headers.get("Content-Type")?.includes("application/json")) {
        return await response.json();
      }
      // 파일 다운로드 같은 다른 경우를 위해 응답 객체 자체를 반환할 수 있도록 처리
      return response as any;
    } finally {
      DOMHelper.setLoadingState(triggerElement, false);
    }
  }

  /**
   * 조회 결과에 따라 데이터 섹션과 업로드 폼의 표시 여부를 토글합니다.
   * @param responseData - API 응답 데이터
   * @returns {boolean} - 데이터가 존재하면 true, 아니면 false
   */
  private toggleSection(responseData: RepoData): boolean {
    if (responseData.items && responseData.items.length > 0) {
      this.dataText.textContent = responseData.items[0];
      this.dwnXlsxButton.classList.remove("hidden");
      this.dataFoundDiv.classList.remove("hidden");
      this.uploadFormDiv.classList.add("hidden");
      return true;
    } else {
      this.dwnXlsxButton.classList.add("hidden");
      this.dataFoundDiv.classList.add("hidden");
      this.uploadFormDiv.classList.remove("hidden");
      NotificationService.alert("조회되는 작업 폴더가 없습니다. 폴더를 업로드 해주세요.");
      return false;
    }
  }

  /**
   * 진행률 데이터를 UI에 렌더링합니다.
   */
  private renderProgress(data: RepoData) {
    const { task_done, review_done, total_done, total } = data;
    const percent = total > 0 ? Math.round((total_done / total) * 100) : 0;

    this.completedText.textContent = `${total_done} / ${total}`;
    this.progressBar.style.width = `${percent}%`;
    this.workedText.textContent = String(task_done);
    this.reviewedText.textContent = String(review_done);
  }

  /**
   * 커밋 목록을 UI에 렌더링합니다.
   */
  private renderCommits(commits: Commit[]) {
    this.commitsContainer.innerHTML = ""; // 기존 내용 초기화
    if (commits && commits.length > 0) {
      commits.forEach((c) => {
        const div = document.createElement("div");
        div.className = "px-4 py-2 mb-2 rounded-lg bg-stone-100";
        div.innerHTML = `
          <p class="font-normal">${c.message}</p>
          <p class="text-sm">${c.author} committed at ${new Date(c.committed_at).toLocaleString()}</p>
        `;
        this.commitsContainer.appendChild(div);
      });
    } else {
      this.commitsContainer.innerHTML = `<p class="text-center text-stone-300">Not Found Yet</p>`;
    }
  }

  // --- 이벤트 핸들러 (Event Handlers) ---

  private async handleLookupRepo(target: HTMLButtonElement) {
    try {
      const repoInfo = this.getRepoInfo(true);
      const result = await this.apiRequest<{ data: { response: RepoData } }>(
        API_ENDPOINTS.LOOKUP_REPO,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(repoInfo),
        },
        target
      );

      const responseData = result.data.response;
      if (this.toggleSection(responseData)) {
        this.renderProgress(responseData);
        this.renderCommits(responseData.commits);
      }
    } catch (err: any) {
      NotificationService.error("오류", err.message);
    }
  }

  private async handleReloadCommits(target: HTMLButtonElement) {
    try {
      const repoInfo = this.getRepoInfo();
      const result = await this.apiRequest<{ data: { response: RepoData } }>(
        API_ENDPOINTS.LOOKUP_REPO,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(repoInfo),
        },
        target
      );
      const responseData = result.data.response;
      this.renderProgress(responseData);
      this.renderCommits(responseData.commits);
    } catch (err: any) {
      NotificationService.error("오류", err.message);
    }
  }

  private async handleDownloadWorkFile(data: string, triggerElement: HTMLButtonElement) {
    DOMHelper.setLoadingState(triggerElement, true);
    try {
      const response = await fetch(API_ENDPOINTS.DOWNLOAD_WORKFILE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: data,
      });

      if (!response.ok) {
        const jsonResponse = await response.json();
        throw new Error(jsonResponse?.error?.message || "다운로드 실패");
      }

      if (response.headers.get("Content-Type")?.includes("application/json")) {
        const jsonResponse = await response.json();
        NotificationService.alert(jsonResponse.data.message);
      } else {
        await DOMHelper.downloadFileFromResponse(response, "download.zip");
      }
    } catch (err: any) {
      NotificationService.error("다운로드 오류", err.message);
    } finally {
      DOMHelper.setLoadingState(triggerElement, false);
    }
  }

  private async handleDownloadWorkList(target: HTMLButtonElement) {
    try {
      const repoInfo = this.getRepoInfo();
      const selectedRadio = document.querySelector<HTMLInputElement>('input[name="download-data-type"]:checked');

      if (!selectedRadio) {
        NotificationService.alert("다운로드할 데이터 타입을 선택해주세요.");
        return;
      }

      const dataToDownload = JSON.stringify({ ...repoInfo, data_type: selectedRadio.id });
      const isPendingData = selectedRadio.id === "pending-data";

      if (isPendingData) {
        const confirmation = await NotificationService.confirm(
          "확인",
          "납품할 데이터를 다운로드 하시겠습니까?\n다운로드 한 후에는 재다운로드를 진행할 수 없습니다."
        );
        if (confirmation.isConfirmed) {
          await this.handleDownloadWorkFile(dataToDownload, target);
        }
      } else {
        await this.handleDownloadWorkFile(dataToDownload, target);
      }
    } catch (err: any) {
      NotificationService.error("오류", err.message);
    }
  }

  private async handleDownloadXlsx(target: HTMLButtonElement) {
    DOMHelper.setLoadingState(target, true);
    try {
      const repoInfo = this.getRepoInfo(true);
      const response = await fetch(API_ENDPOINTS.DOWNLOAD_XLSX, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(repoInfo),
      });

      if (!response.ok) {
        const jsonResponse = await response.json();
        throw new Error(jsonResponse?.error?.message || "다운로드 실패");
      }

      if (response.headers.get("Content-Type")?.includes("application/json")) {
        const jsonResponse = await response.json();
        NotificationService.alert(jsonResponse.data.message);
      } else {
        await DOMHelper.downloadFileFromResponse(response, "download.xlsx");
      }
    } catch (err: any) {
      NotificationService.error("다운로드 오류", err.message);
    } finally {
      DOMHelper.setLoadingState(target, false);
    }
  }

  private async handleDownloadKpi(target: HTMLButtonElement) {
    DOMHelper.setLoadingState(target, true);
    try {
      const repoInfo = this.getRepoInfo();
      const response = await fetch(API_ENDPOINTS.DOWNLOAD_KPI, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(repoInfo),
      });

      if (!response.ok) {
        const jsonResponse = await response.json();
        throw new Error(jsonResponse?.error?.message || "다운로드 실패");
      }

      if (response.headers.get("Content-Type")?.includes("application/json")) {
        const jsonResponse = await response.json();
        NotificationService.alert(jsonResponse?.error?.message);
      } else {
        await DOMHelper.downloadFileFromResponse(response, "download.xlsx");
      }
    } catch (err: any) {
      NotificationService.error("다운로드 오류", err.message);
    } finally {
      DOMHelper.setLoadingState(target, false);
    }
  }

  private async handleUploadWorkFile(file: File) {
    if (!file.name.endsWith(".zip") && file.type !== "application/zip") {
      NotificationService.error("오류", "ZIP 파일만 업로드할 수 있습니다.");
      return;
    }

    try {
      const repoInfo = this.getRepoInfo();

      const confirmation = await NotificationService.confirm(
        "확인",
        "해당 파일을 업로드 하겠습니까? 업로드 후에는 삭제할 수 없습니다."
      );

      if (!confirmation.isConfirmed) {
        this.fileInput.value = "";
        return;
      }

      const formData = new FormData();
      formData.append("workfile", file, file.name);
      formData.append("repo_url", repoInfo.repo_url);
      formData.append("branch", repoInfo.branch);
      formData.append("path", repoInfo.path);

      await this.apiRequest(
        API_ENDPOINTS.UPLOAD_WORKFILE,
        {
          method: "POST",
          body: formData,
        },
        this.uploadFormDiv
      );

      await NotificationService.success("성공", "파일이 성공적으로 업로드되었습니다.");
      // 업로드 성공 후, 자동으로 레포지토리 정보 다시 조회
      await this.handleLookupRepo(this.chkRepoButton);
    } catch (err: any) {
      NotificationService.error("업로드 실패", err.message);
      this.fileInput.value = "";
    }
  }

  private handleDragOver = (event: DragEvent) => {
    event.preventDefault();
    this.dropzoneLabel.classList.add("border-blue-500", "bg-gray-100");
  };

  private handleDragLeave = (event: DragEvent) => {
    event.preventDefault();
    this.dropzoneLabel.classList.remove("border-blue-500", "bg-gray-100");
  };

  private handleDrop = (event: DragEvent) => {
    event.preventDefault();
    this.dropzoneLabel.classList.remove("border-blue-500", "bg-gray-100");
    if (event.dataTransfer?.files.length) {
      this.handleUploadWorkFile(event.dataTransfer.files[0]);
    }
  };

  private async handleS3Upload(target: HTMLButtonElement) {
    try {
      // 1. 레포지토리 정보와 작업 폴더 이름 가져오기
      const repoInfo = this.getRepoInfo();
      const workFolderName = this.dataText.textContent?.trim();

      if (!workFolderName) {
        NotificationService.error("오류", "먼저 'Check Repo'를 통해 작업 폴더를 조회해야 합니다.");
        return;
      }

      // 2. 사용자에게 최종 확인 받기
      const confirmation = await NotificationService.confirm(
        "S3 업로드 확인",
        `'${workFolderName}' 폴더의 최초/최종 JSON 파일들과 KPI 보고서를 S3에 업로드하시겠습니까? 이 작업은 시간이 걸릴 수 있습니다.`
      );

      if (!confirmation.isConfirmed) {
        return; // 사용자가 'No'를 클릭하면 작업 취소
      }

      // 3. 백엔드로 보낼 데이터 준비
      const payload = {
        ...repoInfo,
        work_folder_name: workFolderName,
      };

      // 4. 공용 apiRequest 함수를 사용하여 백엔드 호출
      const result = await this.apiRequest(
        API_ENDPOINTS.S3_UPLOAD_FROM_COMMITS,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        target // 로딩 상태를 표시할 버튼 요소
      );

      // 5. 성공 알림 표시
      await NotificationService.success("업로드 완료", "파일들이 성공적으로 S3에 업로드되었습니다.");
      console.log("S3 Upload Result:", result); // 개발자 확인을 위해 콘솔에 결과 로깅
    } catch (err: any) {
      // 공용 apiRequest에서 처리된 오류 또는 기타 오류를 사용자에게 표시
      NotificationService.error("S3 업로드 오류", err.message);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    new RepoPageManager();
  } catch (error: any) {
    console.error("Failed to initialize RepoPageManager:", error);
    NotificationService.error("초기화 오류", "페이지를 초기화하는 중 문제가 발생했습니다. 콘솔을 확인해주세요.");
  }
});
