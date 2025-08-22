// UI 관련 기능 관리
class UIManager {
    constructor() {
        this.init();
    }

    init() {
        // Lucide 아이콘 초기화
        lucide.createIcons();

        // 필터 토글 기능 초기화
        this.setupFilterToggle();
    }

    setupFilterToggle() {
        const toggleButton = document.getElementById('toggleFilters');
        const filtersContainer = document.getElementById('filtersContainer');
        const toggleIcon = toggleButton.querySelector('i');

        if (!toggleButton || !filtersContainer || !toggleIcon) {
            console.warn('Filter toggle elements not found');
            return;
        }

        toggleButton.addEventListener('click', () => {
            const isOpen = filtersContainer.classList.toggle('open');
            toggleIcon.style.transform = isOpen ? 'rotate(180deg)' : 'rotate(0deg)';
        });
    }
}