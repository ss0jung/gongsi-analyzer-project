// UI 관련 기능 관리
class UIManager {
  constructor() {
    this.init();
  }

  init() {
    // Lucide 아이콘 초기화 (안전 가드)
    if (window.lucide?.createIcons) {
      lucide.createIcons();
    }
    // 필터 토글 초기화
    this.setupFilterToggle();
  }

  setupFilterToggle() {
    const btn = document.getElementById('toggleFilters');
    const box = document.getElementById('filtersContainer');
    if (!btn || !box) return;

    // lucide가 <i>를 <svg>로 치환하므로 svg 우선 탐색
    const icon = btn.querySelector('svg,[data-lucide="chevron-down"]');
    if (icon && !icon.classList.contains('transition-transform')) {
      icon.classList.add('transition-transform');
    }

    // 초기 상태: 닫힘
    box.classList.remove('hidden');          // 혹시 남아있으면 제거
    box.classList.remove('open');            // 기본은 닫힘
    box.style.maxHeight = '0px';             // 높이 0으로 시작 (CSS와 일치)
    btn.setAttribute('aria-controls', 'filtersContainer');
    btn.setAttribute('aria-expanded', 'false');
    if (icon) icon.classList.remove('rotate-180');

    btn.addEventListener('click', (e) => {
      e.preventDefault();

      const willOpen = !box.classList.contains('open');
      box.classList.toggle('open', willOpen);
      btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      if (icon) icon.classList.toggle('rotate-180', willOpen);

      // ✅ 콘텐츠 높이에 맞춰 부드럽게 열기/닫기 (max-height:500px 한계 보완)
      if (willOpen) {
        // 열기: 현재 콘텐츠 높이로 확장
        box.style.maxHeight = box.scrollHeight + 'px';
      } else {
        // 닫기: 0으로
        box.style.maxHeight = '0px';
      }
    });
  }
}
