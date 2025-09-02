// 검색 기능 관리
class SearchManager {
    constructor(formElement, autoCompleteInstance) {
        this.form = formElement;
        this.autoComplete = autoCompleteInstance;

        if (!this.form) {
            console.error('SearchManager: Form element not found');
            return;
        }

        // 팝업 엘리먼트 초기화
        this._ensurePopup();

        this.init();
    }

    init() {
        this.setupFormSubmitListener();
    }

    setupFormSubmitListener() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSearch();
        });
    }

    handleSearch() {
        const selectedCompany = this.autoComplete.getSelectedCompany();

        if (!selectedCompany) {
            alert('목록에서 기업을 선택해주세요.');
            return;
        }

        // 필터 데이터 수집
        const searchData = this.collectSearchData(selectedCompany);

        console.log('Search Data:', searchData);

        // 검색 실행
        this.performSearch(searchData);
    }

   collectSearchData(selectedCompany) {
       // 날짜 범위 수집 (필터에서)
       const dateInputs = document.querySelectorAll('input[type="date"]');
       let beginDate, endDate;

       if (dateInputs.length >= 2 && dateInputs[0].value && dateInputs[1].value) {
           beginDate = this.formatDate(new Date(dateInputs[0].value));
           endDate = this.formatDate(new Date(dateInputs[1].value));
       } else {
           // 기본값: 1년 전부터 현재까지
           endDate = this.formatDate(new Date());
           const beginDateObj = new Date();
           beginDateObj.setFullYear(beginDateObj.getFullYear() - 1);
           beginDate = this.formatDate(beginDateObj);
       }

       // 공시 유형 수집 (단일 선택)
       const selectedType = document.querySelector('input[name="type"]:checked');
       const pblntfTy = selectedType ? selectedType.value : 'A';

       return {
           corpCode: selectedCompany.corpCode,
           beginDe: beginDate,
           endDe: endDate,
           pblntfTy: pblntfTy
       };
   }

    formatDate(date) {
        // YYYYMMDD 형식으로 변환
        return new Date(date.getTime() - (date.getTimezoneOffset() * 60000))
            .toISOString()
            .split('T')[0]
            .replace(/-/g, '');
    }

    async performSearch(searchData) {
        try {
            // 메시지 팝업 표시
            this.showPopup('기업 공시 자료를 검색중입니다. 잠시만 기다려주세요.');

            // 로딩 상태 표시
            this.setLoadingState(true);

            const response = await fetch('/api/v1/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(searchData),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.handleSearchSuccess(data);

        } catch (error) {
            console.error('Search error:', error);
            this.handleSearchError(error);
        } finally {
            // 팝업 닫기 + 로딩 해제
            this.hidePopup();
            this.setLoadingState(false);
        }
    }

    handleSearchSuccess(data) {
        console.log('Search Success:', data);
        try {
            this.displayResults(data);
        } catch (e) {
          console.error('Render error in handleSearchSuccess:', e);
          alert('결과 화면을 그리는 중 오류가 발생했습니다.');
        }
    }

    handleSearchError(error) {
        console.error('Search failed:', error);
        alert('검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    }

    setLoadingState(isLoading) {
        const submitButton = this.form.querySelector('button[type="submit"]');
        if (!submitButton) return;

        if (isLoading) {
            submitButton.disabled = true;
            submitButton.textContent = '검색 중...';
        } else {
            submitButton.disabled = false;
            submitButton.innerHTML = `
                <span class="sm:hidden">핵심 요약 받기</span>
                <span class="hidden sm:inline">기업 조회</span>
            `;
        }
    }

    // ===== 팝업 유틸 =====
    _ensurePopup() {
        if (document.getElementById('search-popup')) return;

        const el = document.createElement('div');
        el.id = 'search-popup';
        el.setAttribute('aria-live', 'polite');
        el.style.cssText = `
            position: fixed; inset: 0; display: none; z-index: 9999;
            align-items: center; justify-content: center;
            background: rgba(0,0,0,0.35);
        `;
        el.innerHTML = `
            <div style="
                max-width: 90%; width: 420px;
                background: #fff; color: #111; padding: 24px;
                border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                font-size: 16px; line-height: 1.5; text-align: center;
            ">
                <div class="spinner" style="
                    margin: 0 auto 16px auto; width: 40px; height: 40px;
                    border: 4px solid #ddd; border-top: 4px solid #007bff;
                    border-radius: 50%; animation: spin 1s linear infinite;
                "></div>
                <div style="font-weight: 600; margin-bottom: 6px;">처리 중</div>
                <div id="search-popup-message">기업 공시 자료를 검색중입니다. 잠시만 기다려주세요.</div>
                <div style="margin-top: 14px; font-size: 12px; opacity: .7;">창은 자동으로 닫힙니다.</div>
            </div>
        `;
        document.body.appendChild(el);

        // ✅ CSS 애니메이션 삽입
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }

    showPopup(message) {
        this._ensurePopup();
        const root = document.getElementById('search-popup');
        const msg = document.getElementById('search-popup-message');
        if (msg) msg.textContent = message;
        if (root) root.style.display = 'flex';
    }

    hidePopup() {
        const root = document.getElementById('search-popup');
        if (root) root.style.display = 'none';
    }

    displayResults(list) {
      this._ensureResultsContainers(); // 컨테이너 보장

      const section = document.getElementById('search-results');
      const meta = document.getElementById('results-meta');
      const wrapper = document.getElementById('results-table-wrapper');

      if (!Array.isArray(list)) list = [];

      const sorted = [...list].sort((a, b) => (b.rceptDt || '').localeCompare(a.rceptDt || ''));
      meta.textContent = `총 ${sorted.length}건`;

      const rows = sorted.map((it) => {
        const date = this._fmtYYYYMMDD(it.rceptDt);
        return `
          <tr>
            <td class="whitespace-nowrap p-2">${date}</td>
            <td class="p-2">${this._badge(it.reportNm)}</td>
            <td class="p-2">${it.corpName}</td>
            <td class="whitespace-nowrap p-2">
              <button
                type="button"
                class="btn-indexing px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-50"
                data-rcept-no="${it.rceptNo}"
                data-corp-code="${it.corpCode}"
                data-corp-name="${it.corpName}"
                data-report-nm="${it.reportNm}"
                data-rcept-dt="${it.rceptDt}"
                aria-label="요약 및 Q&A 보기"
              >
                요약/QA 보기
              </button>
            </td>
          </tr>`;
      }).join('');

      wrapper.innerHTML = `
        <table class="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th class="text-left border-b p-2">접수일</th>
              <th class="text-left border-b p-2">보고서명</th>
              <th class="text-left border-b p-2">기업명</th>
              <th class="text-left border-b p-2">작업</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td class="p-3" colspan="4">결과가 없습니다.</td></tr>`}
          </tbody>
        </table>`;

      section.classList.remove('hidden');

      // 이벤트 위임(한 번만 바인딩)
      this._attachResultsDelegation(wrapper);
    }


    // YYYYMMDD → YYYY-MM-DD
    _fmtYYYYMMDD(s) {
      if (!s || s.length !== 8) return s || '';
      return `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`;
    }

    // 간단 배지 스타일
    _badge(text) {
      return `
        <span style="
          display:inline-block; padding:2px 8px; border-radius:9999px;
          background:#f3f4f6; color:#111827; font-size:12px;"
        >${text}</span>
      `;
    }

    /**
     * 공시 상세 링크 빌더
     * - 기본값: DART 뷰어 패턴 추정
     * - 확실하지 않음: 기관/환경에 따라 URL 패턴이 다를 수 있으니 필요시 주입/환경변수로 교체 권장
     */
    _buildFilingUrl(rceptNo) {
      if (!rceptNo) return '#';
      // 예시: DART 뷰어 (확실하지 않음)
      return `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${encodeURIComponent(rceptNo)}`;
    }

}