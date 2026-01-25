import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# Папка для баз данных групп
DATABASES_DIR = "databases"


class GroupDatabase:
    """База данных для одной группы"""

    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.db_path = self._get_db_path(chat_id)
        self._ensure_dir()
        self._init_db()

    def _get_db_path(self, chat_id: int) -> str:
        """Путь к файлу БД группы"""
        safe_id = str(chat_id).replace("-", "n")
        return os.path.join(DATABASES_DIR, f"group_{safe_id}.db")

    def _ensure_dir(self):
        """Создать папку если нет"""
        os.makedirs(DATABASES_DIR, exist_ok=True)

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Пользователи группы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                cards TEXT DEFAULT '[]',
                coins INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                bio TEXT DEFAULT '',
                profile_photo_id TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_spin TEXT,
                spin_tickets INTEGER DEFAULT 1,
                last_free_ticket TEXT,
                shields INTEGER DEFAULT 0
            )
        ''')
        
        # Проверяем наличие колонки shields и добавляем если нет
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'shields' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN shields INTEGER DEFAULT 0')

        # Ранги
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ranks (
                user_id INTEGER PRIMARY KEY,
                rank_level INTEGER DEFAULT 0,
                custom_title TEXT DEFAULT '',
                promoted_by INTEGER,
                promoted_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Предупреждения
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reason TEXT,
                warned_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        ''')

        # Наказания
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                punishment_type TEXT,
                reason TEXT,
                punished_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Настройки чата (правила и т.д.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Очередь на арену
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS arena_queue (
                user_id INTEGER PRIMARY KEY,
                card_name TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # История боёв
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER,
                player2_id INTEGER,
                winner_id INTEGER,
                player1_card TEXT,
                player2_card TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Проверяем существующую таблицу market_listings
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_listings'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Проверяем колонки существующей таблицы
            cursor.execute("PRAGMA table_info(market_listings)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            # Если есть user_id но нет seller_id - нужна миграция
            if 'user_id' in existing_columns and 'seller_id' not in existing_columns:
                # Создаём новую таблицу с правильной структурой
                cursor.execute('''
                    CREATE TABLE market_listings_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        seller_id INTEGER NOT NULL,
                        card_name TEXT NOT NULL,
                        price INTEGER NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        sold INTEGER DEFAULT 0,
                        buyer_id INTEGER
                    )
                ''')
                
                # Копируем данные
                cursor.execute('''
                    INSERT INTO market_listings_new (id, seller_id, card_name, price, created_at, sold, buyer_id)
                    SELECT id, user_id, card_name, price, created_at, COALESCE(sold, 0), buyer_id 
                    FROM market_listings
                ''')
                
                # Удаляем старую таблицу
                cursor.execute('DROP TABLE market_listings')
                
                # Переименовываем новую
                cursor.execute('ALTER TABLE market_listings_new RENAME TO market_listings')
        else:
            # Создаём новую таблицу с нуля
            cursor.execute('''
                CREATE TABLE market_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_id INTEGER NOT NULL,
                    card_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    sold INTEGER DEFAULT 0,
                    buyer_id INTEGER
                )
            ''')

        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                ПОЛЬЗОВАТЕЛИ
    # ────────────────────────────────────────────────

    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if row:
            # Получаем имена колонок
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            conn.close()
            
            user = dict(zip(columns, row))
            user['cards'] = json.loads(user.get('cards') or '[]')
            user['spin_tickets'] = user.get('spin_tickets') or 0
            user['shields'] = user.get('shields') or 0
            return user
        
        conn.close()
        return None

    def create_user(self, user_id: int, username: str = None, first_name: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, spin_tickets, shields)
            VALUES (?, ?, ?, 1, 0)
        ''', (user_id, username, first_name))

        # Обновляем имя, если изменилось
        cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?
            WHERE user_id = ? 
            AND (username IS NULL OR username != ? OR first_name != ?)
        ''', (username, first_name, user_id, username, first_name))

        conn.commit()
        conn.close()

    def update_user_info(self, user_id: int, username: str = None, first_name: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET username = ?, first_name = ?
            WHERE user_id = ?
        ''', (username, first_name, user_id))
        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                БИЛЕТЫ НА СПИН
    # ────────────────────────────────────────────────

    def get_spin_tickets(self, user_id: int) -> int:
        user = self.get_user(user_id)
        return user.get('spin_tickets', 0) if user else 0

    def add_spin_tickets(self, user_id: int, amount: int = 1):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET spin_tickets = COALESCE(spin_tickets, 0) + ?
            WHERE user_id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()

    def use_spin_ticket(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT spin_tickets FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row and row[0] > 0:
            cursor.execute('''
                UPDATE users 
                SET spin_tickets = spin_tickets - 1, 
                    last_spin = ?
                WHERE user_id = ?
            ''', (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
            return True

        conn.close()
        return False

    def check_and_give_free_ticket(self, user_id: int) -> tuple:
        user = self.get_user(user_id)
        if not user:
            return False, 0

        last_free = user.get('last_free_ticket')

        if not last_free:
            self._give_free_ticket(user_id)
            return True, 0

        try:
            last_time = datetime.fromisoformat(last_free)
            next_time = last_time + timedelta(minutes=30)
            now = datetime.now()

            if now >= next_time:
                self._give_free_ticket(user_id)
                return True, 0
            else:
                remaining = int((next_time - now).total_seconds() / 60) + 1
                return False, remaining
        except Exception:
            self._give_free_ticket(user_id)
            return True, 0

    def _give_free_ticket(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET spin_tickets = COALESCE(spin_tickets, 0) + 1,
                last_free_ticket = ?
            WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()

    def get_time_until_free_ticket(self, user_id: int) -> int:
        user = self.get_user(user_id)
        if not user:
            return 0

        last_free = user.get('last_free_ticket')
        if not last_free:
            return 0

        try:
            last_time = datetime.fromisoformat(last_free)
            next_time = last_time + timedelta(minutes=30)
            now = datetime.now()

            if now >= next_time:
                return 0

            return int((next_time - now).total_seconds() / 60) + 1
        except Exception:
            return 0

    # ────────────────────────────────────────────────
    #                КАРТЫ
    # ────────────────────────────────────────────────

    def add_card(self, user_id: int, card: Dict):
        user = self.get_user(user_id)
        if not user:
            return

        cards = user.get('cards', [])
        cards.append(card)

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET cards = ? WHERE user_id = ?',
                       (json.dumps(cards), user_id))
        conn.commit()
        conn.close()

    def clear_user_cards(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cards = '[]' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
    def remove_card_from_user(self, user_id: int, card_name: str) -> bool:
        """Удалить одну карту определенного типа у пользователя"""
        user = self.get_user(user_id)
        if not user:
            return False
            
        cards = user.get("cards", [])
        
        # Находим и удаляем первую карту с заданным именем
        for i in range(len(cards)):
            if cards[i]["name"] == card_name:
                del cards[i]
                break
        else:
            # Карта не найдена
            return False
            
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cards = ? WHERE user_id = ?",
                      (json.dumps(cards), user_id))
        conn.commit()
        conn.close()
        return True

    # ────────────────────────────────────────────────
    #                МОНЕТЫ И ЩИТЫ
    # ────────────────────────────────────────────────

    def get_coins(self, user_id: int) -> int:
        user = self.get_user(user_id)
        return user.get('coins', 0) if user else 0
        
    def add_shields(self, user_id: int, amount: int):
        """Добавить щиты пользователю"""
        if amount <= 0:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET shields = COALESCE(shields, 0) + ? WHERE user_id = ?',
                       (amount, user_id))
        conn.commit()
        conn.close()
        
    def get_shields(self, user_id: int) -> int:
        """Получить количество щитов у пользователя"""
        user = self.get_user(user_id)
        return user.get('shields', 0) if user else 0
        
    def use_shield(self, user_id: int) -> bool:
        """Использовать щит (если есть)"""
        shields = self.get_shields(user_id)
        if shields <= 0:
            return False
            
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET shields = shields - 1 WHERE user_id = ?',
                       (user_id,))
        conn.commit()
        conn.close()
        return True

    def add_coins(self, user_id: int, amount: int):
        if amount <= 0:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?',
                       (amount, user_id))
        conn.commit()
        conn.close()

    def remove_coins(self, user_id: int, amount: int) -> bool:
        if amount <= 0:
            return True
        if self.get_coins(user_id) < amount:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?',
                       (amount, user_id))
        conn.commit()
        conn.close()
        return True

    def set_coins(self, user_id: int, amount: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                РЫНОК КАРТОЧЕК
    # ────────────────────────────────────────────────

    def add_listing(self, user_id: int, card_name: str, price: int):
        """Выставить карточку на продажу"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO market_listings (seller_id, card_name, price)
            VALUES (?, ?, ?)
        ''', (user_id, card_name, price))
        conn.commit()
        conn.close()

    def get_my_listings(self, user_id: int) -> List[Dict]:
        """Получить активные объявления пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, card_name, price, created_at
            FROM market_listings
            WHERE seller_id = ? AND sold = 0
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "card_name": r[1], "price": r[2], "created_at": r[3]}
            for r in rows
        ]

    def get_all_listings(self) -> List[Dict]:
        """Получить все активные объявления"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, seller_id, card_name, price, created_at 
            FROM market_listings 
            WHERE sold = 0
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        listings = []
        for row in rows:
            listings.append({
                "id": row[0],
                "seller_id": row[1],
                "card_name": row[2],
                "price": row[3],
                "created_at": row[4]
            })
        return listings

    def get_listing_by_id(self, listing_id: int) -> Optional[Dict]:
        """Получить объявление по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, seller_id, card_name, price, created_at, sold
            FROM market_listings 
            WHERE id = ? AND sold = 0
        ''', (listing_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "seller_id": row[1],
                "card_name": row[2],
                "price": row[3],
                "created_at": row[4],
                "sold": row[5]
            }
        return None

    def remove_listing(self, listing_id: int):
        """Удалить объявление"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM market_listings WHERE id = ?', (listing_id,))
        conn.commit()
        conn.close()

    def mark_listing_sold(self, listing_id: int, buyer_id: int):
        """Отметить объявление как проданное"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE market_listings 
            SET sold = 1, buyer_id = ? 
            WHERE id = ?
        ''', (buyer_id, listing_id))
        conn.commit()
        conn.close()

    def get_market_listings(self, limit: int = 15) -> List[Dict]:
        """Получить последние активные лоты на рынке"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, seller_id, card_name, price
            FROM market_listings
            WHERE sold = 0
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "seller_id": r[1], "card_name": r[2], "price": r[3]}
            for r in rows
        ]

    # ────────────────────────────────────────────────
    #                РЕЙТИНГ АРЕНЫ
    # ────────────────────────────────────────────────

    def update_rating(self, user_id: int, rating_change: int, is_win: bool):
        conn = self.get_connection()
        cursor = conn.cursor()

        if is_win:
            cursor.execute('''
                UPDATE users 
                SET rating = MAX(0, rating + ?), 
                    wins = wins + 1
                WHERE user_id = ?
            ''', (rating_change, user_id))
        else:
            cursor.execute('''
                UPDATE users 
                SET rating = MAX(0, rating + ?), 
                    losses = losses + 1
                WHERE user_id = ?
            ''', (rating_change, user_id))

        conn.commit()
        conn.close()

    def reset_user_rating(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET rating = 0, wins = 0, losses = 0 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()

    def get_top_players(self, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, rating, wins, losses
            FROM users
            WHERE rating > 0 OR wins > 0
            ORDER BY rating DESC, wins DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'user_id': r[0], 'username': r[1], 'first_name': r[2],
                'rating': r[3], 'wins': r[4], 'losses': r[5]
            }
            for r in rows
        ]

    def get_top_by_cards(self, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, cards FROM users')
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            cards = json.loads(r[3] or '[]')
            if cards:
                unique = len(set(c['name'] for c in cards))
                result.append({
                    'user_id': r[0], 'username': r[1], 'first_name': r[2],
                    'cards_count': len(cards), 'unique_count': unique
                })

        return sorted(result, key=lambda x: (-x['cards_count'], -x['unique_count']))[:limit]

    def get_top_by_coins(self, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, coins
            FROM users WHERE coins > 0
            ORDER BY coins DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {'user_id': r[0], 'username': r[1], 'first_name': r[2], 'coins': r[3]}
            for r in rows
        ]

    # ────────────────────────────────────────────────
    #                ПРОФИЛЬ
    # ────────────────────────────────────────────────

    def set_bio(self, user_id: int, bio: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET bio = ? WHERE user_id = ?', (bio[:500], user_id))
        conn.commit()
        conn.close()

    def set_profile_photo(self, user_id: int, photo_id: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET profile_photo_id = ? WHERE user_id = ?',
                       (photo_id, user_id))
        conn.commit()
        conn.close()

    def remove_profile_photo(self, user_id: int):
        self.set_profile_photo(user_id, '')

    # ────────────────────────────────────────────────
    #                РАНГИ
    # ────────────────────────────────────────────────

    def get_user_rank(self, user_id: int) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ranks WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'user_id': row[0], 'rank_level': row[1],
                'custom_title': row[2], 'promoted_by': row[3]
            }
        return {'user_id': user_id, 'rank_level': 0, 'custom_title': '', 'promoted_by': None}

    def set_user_rank(self, user_id: int, rank_level: int, custom_title: str = '', promoted_by: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ranks (user_id, rank_level, custom_title, promoted_by, promoted_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, rank_level, custom_title, promoted_by, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_chat_ranks(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.user_id, r.rank_level, r.custom_title, u.username, u.first_name
            FROM ranks r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.rank_level > 0
            ORDER BY r.rank_level DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'user_id': r[0], 'rank_level': r[1], 'custom_title': r[2],
                'username': r[3], 'first_name': r[4]
            }
            for r in rows
        ]

    # ────────────────────────────────────────────────
    #                ВАРНЫ
    # ────────────────────────────────────────────────

    def add_warning(self, user_id: int, reason: str, warned_by: int, duration_hours: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()

        expires_at = None
        if duration_hours:
            expires_at = (datetime.now() + timedelta(hours=duration_hours)).isoformat()

        cursor.execute('''
            INSERT INTO warnings (user_id, reason, warned_by, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, reason, warned_by, expires_at))

        conn.commit()
        conn.close()

    def get_warnings(self, user_id: int) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM warnings 
            WHERE user_id = ? 
            AND expires_at IS NOT NULL 
            AND expires_at < ?
        ''', (user_id, datetime.now().isoformat()))

        cursor.execute('SELECT COUNT(*) FROM warnings WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return count

    def get_warnings_list(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM warnings 
            WHERE user_id = ? 
            AND expires_at IS NOT NULL 
            AND expires_at < ?
        ''', (user_id, datetime.now().isoformat()))

        cursor.execute('''
            SELECT id, reason, warned_by, created_at, expires_at
            FROM warnings 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.commit()
        conn.close()

        return [
            {'id': r[0], 'reason': r[1], 'warned_by': r[2], 'created_at': r[3], 'expires_at': r[4]}
            for r in rows
        ]

    def clear_warnings(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM warnings WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    def remove_one_warning(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM warnings 
            WHERE id = (
                SELECT id FROM warnings 
                WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT 1
            )
        ''', (user_id,))
        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                НАКАЗАНИЯ
    # ────────────────────────────────────────────────

    def add_punishment(self, user_id: int, punishment_type: str, reason: str,
                       punished_by: int, duration_minutes: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()

        expires_at = None
        if duration_minutes:
            expires_at = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat()

        cursor.execute('''
            INSERT INTO punishments (user_id, punishment_type, reason, punished_by, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, punishment_type, reason, punished_by, expires_at))

        conn.commit()
        conn.close()

    def remove_punishment(self, user_id: int, punishment_type: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE punishments 
            SET is_active = 0
            WHERE user_id = ? AND punishment_type = ? AND is_active = 1
        ''', (user_id, punishment_type))
        conn.commit()
        conn.close()

    def get_expired_punishments(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, punishment_type
            FROM punishments
            WHERE is_active = 1 
            AND expires_at IS NOT NULL 
            AND expires_at < ?
        ''', (datetime.now().isoformat(),))
        rows = cursor.fetchall()
        conn.close()

        return [
            {'id': r[0], 'user_id': r[1], 'punishment_type': r[2], 'chat_id': self.chat_id}
            for r in rows
        ]

    def deactivate_punishment(self, punishment_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE punishments SET is_active = 0 WHERE id = ?', (punishment_id,))
        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                ПРАВИЛА ЧАТА
    # ────────────────────────────────────────────────

    def get_rules(self) -> str:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'rules'")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ''

    def set_rules(self, rules: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES ('rules', ?)
        ''', (rules,))
        conn.commit()
        conn.close()

    # ────────────────────────────────────────────────
    #                АРЕНА
    # ────────────────────────────────────────────────

    def join_arena_queue(self, user_id: int, card_name: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO arena_queue (user_id, card_name, joined_at)
            VALUES (?, ?, ?)
        ''', (user_id, card_name, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def leave_arena_queue(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM arena_queue WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    def get_arena_queue(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, card_name, joined_at 
            FROM arena_queue
            ORDER BY joined_at ASC
        ''')
        rows = cursor.fetchall()
        conn.close()

        return [
            {'user_id': r[0], 'card_name': r[1], 'joined_at': r[2]}
            for r in rows
        ]

    def is_in_queue(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM arena_queue WHERE user_id = ?', (user_id,))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def add_battle(self, player1_id: int, player2_id: int, winner_id: int,
                   player1_card: str, player2_card: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO battles (player1_id, player2_id, winner_id, player1_card, player2_card)
            VALUES (?, ?, ?, ?, ?)
        ''', (player1_id, player2_id, winner_id, player1_card, player2_card))
        conn.commit()
        conn.close()


# ────────────────────────────────────────────────
#          DatabaseManager и GlobalDatabase
# ────────────────────────────────────────────────

class DatabaseManager:
    """Менеджер для работы с базами данных разных групп"""

    _instances: Dict[int, GroupDatabase] = {}
    _global_db: Optional['GlobalDatabase'] = None

    @classmethod
    def get_db(cls, chat_id: int) -> GroupDatabase:
        if chat_id not in cls._instances:
            cls._instances[chat_id] = GroupDatabase(chat_id)
        return cls._instances[chat_id]

    @classmethod
    def get_global_db(cls) -> 'GlobalDatabase':
        if cls._global_db is None:
            cls._global_db = GlobalDatabase()
        return cls._global_db

    @classmethod
    def get_all_group_dbs(cls) -> List[GroupDatabase]:
        if os.path.exists(DATABASES_DIR):
            for filename in os.listdir(DATABASES_DIR):
                if filename.startswith('group_') and filename.endswith('.db'):
                    safe_id = filename[6:-3]
                    chat_id = int(safe_id.replace("n", "-"))
                    if chat_id not in cls._instances:
                        cls._instances[chat_id] = GroupDatabase(chat_id)
        return list(cls._instances.values())


class GlobalDatabase:
    """Глобальная БД для общих данных (поиск по username и т.д.)"""

    def __init__(self):
        os.makedirs(DATABASES_DIR, exist_ok=True)
        self.db_path = os.path.join(DATABASES_DIR, "global.db")
        self._init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users_global (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_seen TEXT
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON users_global(username)')
        
        # Таблица для хранения бустов шанса спина
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spin_boosts (
                user_id INTEGER PRIMARY KEY,
                multiplier REAL NOT NULL DEFAULT 1.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def update_user(self, user_id: int, username: str = None, first_name: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users_global (user_id, username, first_name, last_seen)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def find_by_username(self, username: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name 
            FROM users_global 
            WHERE LOWER(username) = LOWER(?)
        ''', (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'user_id': row[0], 'username': row[1], 'first_name': row[2]}
        return None
    
    # === ФУНКЦИИ ДЛЯ РАБОТЫ С БУСТАМИ СПИНА ===
    
    def set_spin_boost(self, user_id: int, multiplier: float, duration_hours: int = None):
        """Установить буст шанса спина для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        expires_at = None
        if duration_hours:
            expires_at = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO spin_boosts (user_id, multiplier, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, multiplier, datetime.now().isoformat(), expires_at))
        
        conn.commit()
        conn.close()

    def get_spin_boost(self, user_id: int) -> float:
        """Получить текущий буст шанса спина для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Удаляем истекшие бусты
        cursor.execute('''
            DELETE FROM spin_boosts 
            WHERE user_id = ? 
            AND expires_at IS NOT NULL 
            AND expires_at < ?
        ''', (user_id, datetime.now().isoformat()))
        
        cursor.execute('''
            SELECT multiplier FROM spin_boosts 
            WHERE user_id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        
        return row[0] if row else 1.0

    def remove_spin_boost(self, user_id: int):
        """Удалить буст шанса спина для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM spin_boosts WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    def get_expired_spin_boosts(self) -> List[int]:
        """Получить список пользователей с истекшими бустами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id FROM spin_boosts
            WHERE expires_at IS NOT NULL 
            AND expires_at < ?
        ''', (datetime.now().isoformat(),))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]


# Для обратной совместимости со старым кодом
class LegacyDB:
    def get_connection(self):
        raise NotImplementedError("Use DatabaseManager.get_db(chat_id) instead")

    def get_user(self, user_id: int, chat_id: int = None):
        if chat_id:
            return DatabaseManager.get_db(chat_id).get_user(user_id)
        return None

    def create_user(self, user_id: int, username: str = None, first_name: str = None, chat_id: int = None):
        if chat_id:
            DatabaseManager.get_db(chat_id).create_user(user_id, username, first_name)
        DatabaseManager.get_global_db().update_user(user_id, username, first_name)


# Экземпляр для совместимости
db = LegacyDB()