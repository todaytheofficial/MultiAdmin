const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// Парсинг JSON
app.use(express.json());

// Статические файлы
app.use(express.static(path.join(__dirname, 'public')));

// Путь к файлу статистики
const DATA_DIR = path.join(__dirname, 'data');
const STATS_PATH = path.join(DATA_DIR, 'stats.json');

// Создаём папку data если её нет
if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}

// API для получения статистики
app.get('/api/stats', (req, res) => {
    if (fs.existsSync(STATS_PATH)) {
        try {
            const data = fs.readFileSync(STATS_PATH, 'utf8');
            const stats = JSON.parse(data);
            res.json(stats);
        } catch (err) {
            console.error('Ошибка чтения stats.json:', err);
            res.json(getDefaultStats());
        }
    } else {
        res.json(getDefaultStats());
    }
});

// API для обновления статистики (вызывается ботом)
app.post('/api/update-stats', (req, res) => {
    try {
        const stats = req.body;
        
        // Валидация
        if (!stats || typeof stats !== 'object') {
            return res.status(400).json({ error: 'Invalid data' });
        }
        
        // Проверяем обязательные поля
        const requiredFields = ['groups', 'users', 'total_cards', 'battles'];
        for (const field of requiredFields) {
            if (typeof stats[field] !== 'number') {
                stats[field] = 0;
            }
        }
        
        // Добавляем время обновления если нет
        if (!stats.updated_at) {
            stats.updated_at = new Date().toISOString();
        }
        
        // Сохраняем
        fs.writeFileSync(STATS_PATH, JSON.stringify(stats, null, 2), 'utf8');
        
        console.log(`📊 [${new Date().toLocaleTimeString()}] Статистика обновлена: ${stats.users} юзеров, ${stats.groups} групп, ${stats.total_cards} карт`);
        res.json({ success: true, received: stats });
    } catch (err) {
        console.error('Ошибка сохранения статистики:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// API для получения редкостей карт
app.get('/api/rarities', (req, res) => {
    if (fs.existsSync(STATS_PATH)) {
        try {
            const data = fs.readFileSync(STATS_PATH, 'utf8');
            const stats = JSON.parse(data);
            res.json(stats.cards_by_rarity || {});
        } catch (err) {
            res.json({});
        }
    } else {
        res.json({});
    }
});

// Проверка здоровья
app.get('/api/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        hasStats: fs.existsSync(STATS_PATH)
    });
});

function getDefaultStats() {
    return {
        groups: 0,
        users: 0,
        total_cards: 0,
        battles: 0,
        cards_by_rarity: {},
        updated_at: null
    };
}

// Главная страница
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 404 для остальных
app.use((req, res) => {
    res.status(404).sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`🌐 Сайт запущен: http://localhost:${PORT}`);
    console.log(`📊 API статистики: http://localhost:${PORT}/api/stats`);
    console.log(`💾 Данные сохраняются в: ${STATS_PATH}`);
});