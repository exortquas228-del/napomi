const tg = window.Telegram?.WebApp;

// Инициализация Telegram WebApp
if (tg) {
    tg.ready();
    tg.expand();
    try {
        if (tg.setHeaderColor) tg.setHeaderColor('#0A0A0C');
        if (tg.setBackgroundColor) tg.setBackgroundColor('#0A0A0C');
    } catch (e) {
        // Игнорируем в старых версиях клиента
    }
}

// Тактильный отклик (Haptic Feedback)
function hapticLight() {
    try {
        tg?.HapticFeedback?.impactOccurred('light');
    } catch (e) {}
}

function hapticMedium() {
    try {
        tg?.HapticFeedback?.impactOccurred('medium');
    } catch (e) {}
}

function hapticSuccess() {
    try {
        tg?.HapticFeedback?.notificationOccurred('success');
    } catch (e) {}
}

// Определение ID пользователя
function getUserId() {
    if (tg?.initDataUnsafe?.user?.id) {
        return tg.initDataUnsafe.user.id;
    }
    const urlParams = new URLSearchParams(window.location.search);
    const paramId = urlParams.get('user_id');
    if (paramId) {
        localStorage.setItem('cached_tg_user_id', paramId);
        return parseInt(paramId, 10);
    }
    const cached = localStorage.getItem('cached_tg_user_id');
    if (cached) return parseInt(cached, 10);
    return 10001; // ID по умолчанию для отладки в браузере
}

const USER_ID = getUserId();

// Глобальное состояние приложения
let eventsList = [];
let editingEventId = null;
let selectedDateStr = getFormattedDate(new Date(Date.now() + 86400000));
let hasExactTime = false;
let currentCalYear = new Date().getFullYear();
let currentCalMonth = new Date().getMonth();

const MONTH_NAMES = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

function getFormattedDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Уведомления Toast
function showToast(message) {
    const toast = document.getElementById('toastNotice');
    const toastText = document.getElementById('toastText');
    if (!toast || !toastText) return;
    toastText.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2400);
}

// Загрузка событий с API
async function loadEvents() {
    try {
        const response = await fetch(`/api/events?user_id=${USER_ID}`);
        if (!response.ok) throw new Error('Сетевая ошибка');
        const data = await response.json();
        eventsList = data.events || [];
        renderEvents();
        updateCounterBadge();
    } catch (err) {
        console.error('Ошибка загрузки событий:', err);
    }
}

// Обновление бейджа счетчика
function updateCounterBadge() {
    const badge = document.getElementById('eventsCountBadge');
    if (badge) {
        badge.textContent = `${eventsList.length} активных`;
    }
}

// Отрисовка списка событий
function renderEvents() {
    const container = document.getElementById('eventsListContainer');
    const emptyState = document.getElementById('emptyState');
    if (!container || !emptyState) return;

    if (eventsList.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'flex';
        return;
    }

    emptyState.style.display = 'none';
    container.innerHTML = eventsList.map(event => createEventCardHtml(event)).join('');
    updateCountdowns();
}

// Генерация HTML карточки события
function createEventCardHtml(event) {
    const hasTime = Boolean(event.has_time);
    const dateFormatted = formatDateDisplay(event.target_date);
    const timeFormatted = hasTime && event.target_time ? ` ${event.target_time}` : '';

    return `
    <div class="event-card" id="card-${event.id}">
        <div class="event-card-header">
            <div>
                <h3 class="event-title">${escapeHtml(event.title)}</h3>
                <div class="event-meta">
                    ${getIcon('calendar', 'icon-meta')}
                    <span>${dateFormatted}${timeFormatted}</span>
                </div>
            </div>
            <div class="event-actions">
                <button class="action-btn" onclick="openEditModal(${event.id})" aria-label="Редактировать">
                    ${getIcon('edit')}
                </button>
                <button class="action-btn btn-delete" onclick="handleDeleteEvent(${event.id})" aria-label="Удалить">
                    ${getIcon('trash')}
                </button>
            </div>
        </div>

        <div id="countdown-${event.id}">
            <!-- Живой счетчик наполняется функцией updateCountdowns -->
        </div>

        <div class="progress-container">
            <div class="progress-header">
                <span id="progress-percent-${event.id}">0%</span>
                <span id="progress-status-${event.id}">В процессе</span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="progress-fill-${event.id}" style="width: 0%"></div>
            </div>
        </div>
    </div>
    `;
}

// Живой таймер обратного отсчета
function updateCountdowns() {
    const now = Date.now();

    eventsList.forEach(event => {
        const container = document.getElementById(`countdown-${event.id}`);
        const fillBar = document.getElementById(`progress-fill-${event.id}`);
        const percentText = document.getElementById(`progress-percent-${event.id}`);
        const statusText = document.getElementById(`progress-status-${event.id}`);

        if (!container) return;

        const targetTime = new Date(event.target_datetime).getTime();
        const createdTime = new Date(event.created_at).getTime();
        const diff = targetTime - now;
        const hasTime = Boolean(event.has_time);

        // Расчет прогресса
        const totalDuration = Math.max(1, targetTime - createdTime);
        const elapsed = Math.max(0, now - createdTime);
        const percent = Math.min(100, Math.max(0, Math.floor((elapsed / totalDuration) * 100)));

        if (fillBar) fillBar.style.width = `${percent}%`;
        if (percentText) percentText.textContent = `${percent}%`;

        if (diff <= 0) {
            container.innerHTML = `
                <div class="completed-banner">
                    ${getIcon('check')}
                    <span>Событие наступило</span>
                </div>
            `;
            if (statusText) statusText.textContent = 'Завершено';
            if (fillBar) fillBar.style.width = '100%';
            if (percentText) percentText.textContent = '100%';
            return;
        }

        if (statusText) statusText.textContent = 'Осталось';

        const totalSeconds = Math.floor(diff / 1000);
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (hasTime) {
            container.innerHTML = `
                <div class="countdown-grid">
                    <div class="countdown-cell">
                        <span class="countdown-number">${days}</span>
                        <span class="countdown-label">Дни</span>
                    </div>
                    <div class="countdown-cell">
                        <span class="countdown-number">${String(hours).padStart(2, '0')}</span>
                        <span class="countdown-label">Часы</span>
                    </div>
                    <div class="countdown-cell">
                        <span class="countdown-number">${String(minutes).padStart(2, '0')}</span>
                        <span class="countdown-label">Мин</span>
                    </div>
                    <div class="countdown-cell">
                        <span class="countdown-number">${String(seconds).padStart(2, '0')}</span>
                        <span class="countdown-label">Сек</span>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="countdown-grid cols-2">
                    <div class="countdown-cell">
                        <span class="countdown-number">${days}</span>
                        <span class="countdown-label">Дни</span>
                    </div>
                    <div class="countdown-cell">
                        <span class="countdown-number">${String(hours).padStart(2, '0')}</span>
                        <span class="countdown-label">Часы</span>
                    </div>
                </div>
            `;
        }
    });
}

// Запуск интервала тикания
setInterval(updateCountdowns, 1000);

// Управление модальным окном создания / редактирования
function openCreateModal() {
    hapticLight();
    editingEventId = null;
    document.getElementById('modalSheetTitle').textContent = 'Новое напоминание';
    document.getElementById('inputEventTitle').value = '';
    
    // По умолчанию дата - завтра
    const tomorrow = new Date(Date.now() + 86400000);
    selectedDateStr = getFormattedDate(tomorrow);
    currentCalYear = tomorrow.getFullYear();
    currentCalMonth = tomorrow.getMonth();

    hasExactTime = false;
    updateToggleState();

    document.getElementById('selectHour').value = '12';
    document.getElementById('selectMinute').value = '00';

    renderCalendar();
    highlightActivePresetChip();

    const overlay = document.getElementById('modalOverlay');
    overlay.classList.add('active');
    setTimeout(() => {
        document.getElementById('inputEventTitle')?.focus();
    }, 250);
}

function openEditModal(eventId) {
    hapticLight();
    const event = eventsList.find(e => e.id === eventId);
    if (!event) return;

    editingEventId = eventId;
    document.getElementById('modalSheetTitle').textContent = 'Редактировать событие';
    document.getElementById('inputEventTitle').value = event.title;

    selectedDateStr = event.target_date;
    const parts = selectedDateStr.split('-');
    if (parts.length === 3) {
        currentCalYear = parseInt(parts[0], 10);
        currentCalMonth = parseInt(parts[1], 10) - 1;
    }

    hasExactTime = Boolean(event.has_time);
    updateToggleState();

    if (hasExactTime && event.target_time) {
        const timeParts = event.target_time.split(':');
        if (timeParts.length >= 2) {
            document.getElementById('selectHour').value = timeParts[0];
            document.getElementById('selectMinute').value = timeParts[1];
        }
    }

    renderCalendar();
    highlightActivePresetChip();

    const overlay = document.getElementById('modalOverlay');
    overlay.classList.add('active');
}

function closeModal() {
    hapticLight();
    const overlay = document.getElementById('modalOverlay');
    overlay.classList.remove('active');
    editingEventId = null;
}

// Переключение тумблера "Указать точное время"
function toggleExactTime() {
    hapticLight();
    hasExactTime = !hasExactTime;
    updateToggleState();
}

function updateToggleState() {
    const toggle = document.getElementById('exactTimeToggle');
    const accordion = document.getElementById('timePickerAccordion');
    if (hasExactTime) {
        toggle.classList.add('active');
        accordion.classList.add('open');
    } else {
        toggle.classList.remove('active');
        accordion.classList.remove('open');
    }
}

// Кастомный календарь
function renderCalendar() {
    const monthTitle = document.getElementById('calMonthTitle');
    const daysGrid = document.getElementById('calDaysGrid');
    if (!monthTitle || !daysGrid) return;

    monthTitle.textContent = `${MONTH_NAMES[currentCalMonth]} ${currentCalYear}`;

    const firstDayIndex = new Date(currentCalYear, currentCalMonth, 1).getDay();
    // Корректировка под понедельник как первый день недели (0 = Пн, 6 = Вс)
    const startOffset = (firstDayIndex + 6) % 7;
    const daysInMonth = new Date(currentCalYear, currentCalMonth + 1, 0).getDate();

    const todayStr = getFormattedDate(new Date());

    let html = '';
    for (let i = 0; i < startOffset; i++) {
        html += '<div class="calendar-day-tile empty"></div>';
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const monthNum = String(currentCalMonth + 1).padStart(2, '0');
        const dayNum = String(day).padStart(2, '0');
        const tileDateStr = `${currentCalYear}-${monthNum}-${dayNum}`;

        const isPast = tileDateStr < todayStr;
        const isToday = tileDateStr === todayStr;
        const isSelected = tileDateStr === selectedDateStr;

        let classes = 'calendar-day-tile';
        if (isPast) classes += ' disabled';
        if (isToday) classes += ' today';
        if (isSelected) classes += ' selected';

        html += `
            <div class="${classes}" onclick="handleSelectDay('${tileDateStr}')">
                ${day}
            </div>
        `;
    }

    daysGrid.innerHTML = html;
}

function handleSelectDay(dateStr) {
    hapticMedium();
    selectedDateStr = dateStr;
    renderCalendar();
    highlightActivePresetChip();
}

function prevMonth() {
    hapticLight();
    currentCalMonth--;
    if (currentCalMonth < 0) {
        currentCalMonth = 11;
        currentCalYear--;
    }
    renderCalendar();
}

function nextMonth() {
    hapticLight();
    currentCalMonth++;
    if (currentCalMonth > 11) {
        currentCalMonth = 0;
        currentCalYear++;
    }
    renderCalendar();
}

function selectPresetDays(offsetDays) {
    hapticLight();
    const d = new Date(Date.now() + offsetDays * 86400000);
    selectedDateStr = getFormattedDate(d);
    currentCalYear = d.getFullYear();
    currentCalMonth = d.getMonth();
    renderCalendar();
    highlightActivePresetChip();
}

function highlightActivePresetChip() {
    const todayStr = getFormattedDate(new Date());
    const tomorrowStr = getFormattedDate(new Date(Date.now() + 86400000));
    const day7Str = getFormattedDate(new Date(Date.now() + 7 * 86400000));
    const day30Str = getFormattedDate(new Date(Date.now() + 30 * 86400000));

    document.querySelectorAll('.preset-chip').forEach(chip => chip.classList.remove('active'));

    if (selectedDateStr === todayStr) {
        document.getElementById('chip-today')?.classList.add('active');
    } else if (selectedDateStr === tomorrowStr) {
        document.getElementById('chip-tomorrow')?.classList.add('active');
    } else if (selectedDateStr === day7Str) {
        document.getElementById('chip-7d')?.classList.add('active');
    } else if (selectedDateStr === day30Str) {
        document.getElementById('chip-30d')?.classList.add('active');
    }
}

// Сохранение события
async function handleSaveEvent() {
    const title = document.getElementById('inputEventTitle').value.trim();
    if (!title) {
        showToast('Введите название события');
        hapticLight();
        document.getElementById('inputEventTitle')?.focus();
        return;
    }

    if (!selectedDateStr) {
        showToast('Выберите дату');
        return;
    }

    let targetTime = '';
    if (hasExactTime) {
        const hour = document.getElementById('selectHour').value;
        const min = document.getElementById('selectMinute').value;
        targetTime = `${hour}:${min}`;
    }

    const payload = {
        user_id: USER_ID,
        title: title,
        target_date: selectedDateStr,
        target_time: targetTime,
        has_time: hasExactTime
    };

    const submitBtn = document.getElementById('btnSubmitModal');
    submitBtn.disabled = true;

    try {
        let response;
        if (editingEventId) {
            response = await fetch(`/api/events/${editingEventId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            response = await fetch('/api/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Ошибка при сохранении');
        }

        hapticSuccess();
        showToast(editingEventId ? 'Событие обновлено' : 'Событие добавлено');
        closeModal();
        await loadEvents();
    } catch (err) {
        console.error('Ошибка сохранения:', err);
        showToast('Не удалось сохранить событие');
    } finally {
        submitBtn.disabled = false;
    }
}

// Удаление события
async function handleDeleteEvent(eventId) {
    hapticMedium();
    if (!confirm('Удалить это напоминание?')) return;

    try {
        const response = await fetch(`/api/events/${eventId}?user_id=${USER_ID}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Ошибка удаления');

        hapticSuccess();
        showToast('Событие удалено');
        await loadEvents();
    } catch (err) {
        console.error('Ошибка при удалении:', err);
        showToast('Не удалось удалить событие');
    }
}

// Вспомогательные функции
function formatDateDisplay(isoDate) {
    if (!isoDate) return '';
    const parts = isoDate.split('-');
    if (parts.length === 3) {
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
    return isoDate;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Вставка SVG иконок
    const brandIcon = document.getElementById('brandIconContainer');
    if (brandIcon) brandIcon.innerHTML = getIcon('sparkle');

    const emptyIcon = document.getElementById('emptyIconContainer');
    if (emptyIcon) emptyIcon.innerHTML = getIcon('bell');

    const btnAddIcon = document.getElementById('btnAddIconContainer');
    if (btnAddIcon) btnAddIcon.innerHTML = getIcon('plus');

    const btnSaveIcon = document.getElementById('btnSaveIconContainer');
    if (btnSaveIcon) btnSaveIcon.innerHTML = getIcon('check');

    const calPrev = document.getElementById('calPrevBtn');
    if (calPrev) calPrev.innerHTML = getIcon('chevronLeft');

    const calNext = document.getElementById('calNextBtn');
    if (calNext) calNext.innerHTML = getIcon('chevronRight');

    const sheetClose = document.getElementById('sheetCloseBtn');
    if (sheetClose) sheetClose.innerHTML = getIcon('close');

    // Наполнение селекторов времени
    const selectHour = document.getElementById('selectHour');
    const selectMinute = document.getElementById('selectMinute');
    if (selectHour && selectMinute) {
        for (let h = 0; h < 24; h++) {
            const val = String(h).padStart(2, '0');
            selectHour.innerHTML += `<option value="${val}">${val}</option>`;
        }
        for (let m = 0; m < 60; m += 5) {
            const val = String(m).padStart(2, '0');
            selectMinute.innerHTML += `<option value="${val}">${val}</option>`;
        }
    }

    loadEvents();
});
