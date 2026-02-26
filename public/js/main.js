// ========== Тема ==========
const themeToggle = document.getElementById('themeToggle');
const themeToggleMobile = document.getElementById('themeToggleMobile');

// Получить сохранённую тему или системную
function getPreferredTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) return saved;
    
    // Проверяем системные настройки
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Применить тему
function setTheme(theme) {
    // Добавляем класс для анимации
    document.body.classList.add('theme-transition');
    
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Обновляем текст в мобильном меню
    const label = document.querySelector('.theme-label');
    if (label) {
        label.textContent = theme === 'dark' ? 'Тёмная тема' : 'Светлая тема';
    }
    
    // Убираем класс анимации после завершения
    setTimeout(() => {
        document.body.classList.remove('theme-transition');
    }, 300);
}

// Переключить тему
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = current === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

// Инициализация темы (сразу, до загрузки DOM)
(function() {
    const theme = getPreferredTheme();
    document.documentElement.setAttribute('data-theme', theme);
})();

// Слушаем изменения системной темы
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
        setTheme(e.matches ? 'dark' : 'light');
    }
});


// ========== DOM Ready ==========
document.addEventListener('DOMContentLoaded', () => {
    
    // Привязываем обработчики темы после загрузки DOM
    const themeBtn = document.getElementById('themeToggle');
    const themeBtnMobile = document.getElementById('themeToggleMobile');
    
    if (themeBtn) {
        themeBtn.addEventListener('click', toggleTheme);
    }
    
    if (themeBtnMobile) {
        themeBtnMobile.addEventListener('click', toggleTheme);
    }
    
    // Обновляем label при загрузке
    const label = document.querySelector('.theme-label');
    if (label) {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        label.textContent = currentTheme === 'dark' ? 'Тёмная тема' : 'Светлая тема';
    }


    // ========== Мобильное меню ==========
    const burger = document.getElementById('burger');
    const mobileMenu = document.getElementById('mobileMenu');

    if (burger && mobileMenu) {
        burger.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            burger.classList.toggle('active');
        });

        // Закрытие при клике на ссылку
        document.querySelectorAll('.mobile-menu a').forEach(link => {
            link.addEventListener('click', () => {
                mobileMenu.classList.remove('active');
                burger.classList.remove('active');
            });
        });

        // Закрытие при клике вне меню
        document.addEventListener('click', (e) => {
            if (!mobileMenu.contains(e.target) && !burger.contains(e.target)) {
                mobileMenu.classList.remove('active');
                burger.classList.remove('active');
            }
        });
    }


    // ========== Табы ==========
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const panel = document.getElementById('tab-' + tab);
            if (panel) {
                panel.classList.add('active');
            }
        });
    });


    // ========== 3D Floating Card ==========
    const floatingCard = document.getElementById('floatingCard');

    if (floatingCard) {
        let isHovering = false;
        let isFlipped = false;
        
        // Mouse enter - останавливаем анимацию
        floatingCard.addEventListener('mouseenter', () => {
            if (window.innerWidth <= 768) return;
            isHovering = true;
            floatingCard.style.animation = 'none';
        });
        
        // Mouse leave - возвращаем анимацию
        floatingCard.addEventListener('mouseleave', () => {
            if (window.innerWidth <= 768) return;
            isHovering = false;
            
            floatingCard.style.transition = 'transform 0.5s ease-out';
            floatingCard.style.transform = '';
            
            setTimeout(() => {
                if (!isHovering) {
                    floatingCard.style.transition = '';
                    floatingCard.style.animation = 'floatCard 8s ease-in-out infinite';
                }
            }, 500);
        });
        
        // Mouse move - 3D эффект
        floatingCard.addEventListener('mousemove', (e) => {
            if (!isHovering || window.innerWidth <= 768) return;
            
            const rect = floatingCard.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = (y - centerY) / 8;
            const rotateY = (centerX - x) / 8;
            
            floatingCard.style.transition = 'transform 0.1s ease-out';
            floatingCard.style.transform = `
                perspective(1500px)
                rotateX(${rotateX}deg)
                rotateY(${rotateY}deg)
                translateZ(30px)
                scale(1.05)
            `;
        });
        
        // Клик для переворота (на всех устройствах)
        floatingCard.addEventListener('click', () => {
            const cardInner = floatingCard.querySelector('.card-inner');
            if (!cardInner) return;
            
            isFlipped = !isFlipped;
            cardInner.style.transform = isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)';
        });
    }


    // ========== Parallax для баннера ==========
    const cardBanner = document.querySelector('.card-banner');
    const bannerParticles = document.querySelector('.banner-particles');

    if (cardBanner && bannerParticles && window.innerWidth > 768) {
        let ticking = false;
        
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    const scrolled = window.pageYOffset;
                    const bannerHeight = cardBanner.offsetHeight;
                    
                    if (scrolled < bannerHeight) {
                        bannerParticles.style.transform = `translateY(${scrolled * 0.3}px)`;
                    }
                    ticking = false;
                });
                ticking = true;
            }
        });
    }


    // ========== Шапка при скролле ==========
    const header = document.getElementById('header');

    if (header) {
        let lastScroll = 0;
        
        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;
            
            if (currentScroll > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
            
            lastScroll = currentScroll;
        });
    }


    // ========== Предзагрузка изображений ==========
    const imagesToPreload = ['/images/pashalka.jpg', '/images/card.jpg'];
    imagesToPreload.forEach(src => {
        const img = new Image();
        img.src = src;
    });

});


// ========== Анимация счётчиков ==========
function animateCounter(element, target) {
    if (!element) return;
    
    const duration = 1500;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing - ease out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (target - start) * easeOut);
        
        element.textContent = current.toLocaleString('ru-RU');
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}


// ========== Загрузка статистики ==========
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        
        if (!response.ok) {
            throw new Error('Failed to fetch stats');
        }
        
        const data = await response.json();

        const elements = {
            groups: document.getElementById('stat-groups'),
            users: document.getElementById('stat-users'),
            cards: document.getElementById('stat-cards'),
            battles: document.getElementById('stat-battles')
        };

        // Анимируем счётчики
        if (elements.groups) {
            if (data.groups > 0) {
                animateCounter(elements.groups, data.groups);
            } else {
                elements.groups.textContent = '—';
            }
        }

        if (elements.users) {
            if (data.users > 0) {
                animateCounter(elements.users, data.users);
            } else {
                elements.users.textContent = '—';
            }
        }

        if (elements.cards) {
            if (data.total_cards > 0) {
                animateCounter(elements.cards, data.total_cards);
            } else {
                elements.cards.textContent = '—';
            }
        }

        if (elements.battles) {
            if (data.battles > 0) {
                animateCounter(elements.battles, data.battles);
            } else {
                elements.battles.textContent = '—';
            }
        }

    } catch (error) {
        console.log('Статистика недоступна:', error.message);
        
        // Показываем прочерки при ошибке
        ['stat-groups', 'stat-users', 'stat-cards', 'stat-battles'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '—';
        });
    }
}


// ========== Intersection Observer для статистики ==========
const statsSection = document.getElementById('stats');
let statsLoaded = false;

if (statsSection) {
    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !statsLoaded) {
                statsLoaded = true;
                loadStats();
                statsObserver.unobserve(entry.target);
            }
        });
    }, { 
        threshold: 0.2,
        rootMargin: '50px'
    });

    statsObserver.observe(statsSection);
}


// ========== Анимация появления элементов ==========
const animatedElements = document.querySelectorAll('.feature-card, .stat-card, .rarity-item');

if (animatedElements.length > 0) {
    const appearObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Задержка для каскадного эффекта
                setTimeout(() => {
                    entry.target.classList.add('appeared');
                }, index * 50);
                appearObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '20px'
    });

    animatedElements.forEach(el => {
        el.classList.add('animate-on-scroll');
        appearObserver.observe(el);
    });
}


// ========== Smooth Scroll для якорных ссылок ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        
        if (href === '#') return;
        
        const target = document.querySelector(href);
        
        if (target) {
            e.preventDefault();
            
            const headerHeight = document.getElementById('header')?.offsetHeight || 70;
            const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;
            
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});


// ========== Keyboard Navigation ==========
document.addEventListener('keydown', (e) => {
    // Escape закрывает мобильное меню
    if (e.key === 'Escape') {
        const mobileMenu = document.getElementById('mobileMenu');
        const burger = document.getElementById('burger');
        
        if (mobileMenu?.classList.contains('active')) {
            mobileMenu.classList.remove('active');
            burger?.classList.remove('active');
        }
    }
    
    // T переключает тему
    if (e.key === 't' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const activeElement = document.activeElement;
        const isInput = activeElement.tagName === 'INPUT' || 
                       activeElement.tagName === 'TEXTAREA' ||
                       activeElement.isContentEditable;
        
        if (!isInput) {
            toggleTheme();
        }
    }
});


