// 자동완성 기능 관리
class AutoComplete {
    constructor(inputElement, resultsContainer) {
        this.input = inputElement;
        this.results = resultsContainer;
        this.debounceTimer = null;
        this.selectedCompany = null;

        if (!this.input || !this.results) {
            console.error('AutoComplete: Required elements not found');
            return;
        }

        this.init();
    }

    init() {
        this.setupInputListener();
        this.setupOutsideClickListener();
    }

    // 디바운스 함수
    debounce(func, delay) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(func, delay);
    }

    setupInputListener() {
        this.input.addEventListener('input', () => {
            const query = this.input.value;
            this.selectedCompany = null; // 입력값이 변경되면 선택된 회사 정보 초기화

            if (query.length < 1) {
                this.hideResults();
                return;
            }

            // 300ms 디바운싱 적용
            this.debounce(() => {
                this.fetchCompanies(query);
            }, 300);
        });
    }

    setupOutsideClickListener() {
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.results.contains(e.target)) {
                this.hideResults();
            }
        });
    }

    async fetchCompanies(query) {
        try {
            const response = await fetch(`/api/v1/search/companies?query=${encodeURIComponent(query)}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const companies = await response.json();
            this.displayResults(companies);
        } catch (error) {
            console.error('Error fetching companies:', error);
            this.hideResults();
        }
    }

    displayResults(companies) {
        // 이전 결과 삭제
        this.results.innerHTML = '';

        if (!companies || companies.length === 0) {
            this.hideResults();
            return;
        }

        const list = document.createElement('ul');
        list.className = 'absolute w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-60 overflow-y-auto';

        // 최대 10개만 표시
        companies.slice(0, 10).forEach(company => {
            const item = document.createElement('li');
            item.className = 'px-4 py-2 hover:bg-gray-100 cursor-pointer';
            item.textContent = company.corpName;

            item.addEventListener('click', () => {
                this.selectCompany(company);
            });

            list.appendChild(item);
        });

        this.results.appendChild(list);
        this.showResults();
    }

    selectCompany(company) {
        this.input.value = company.corpName;
        this.selectedCompany = company;
        this.hideResults();

        // 회사 선택 이벤트 발생
        this.input.dispatchEvent(new CustomEvent('companySelected', {
            detail: { company: company }
        }));
    }

    showResults() {
        this.results.style.display = 'block';
    }

    hideResults() {
        this.results.innerHTML = '';
        this.results.style.display = 'none';
    }

    getSelectedCompany() {
        return this.selectedCompany;
    }

    clearSelection() {
        this.selectedCompany = null;
    }
}