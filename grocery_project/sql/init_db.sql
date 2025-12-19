DROP VIEW IF EXISTS view_sales_analysis;
DROP TABLE IF EXISTS write_offs CASCADE;
DROP TABLE IF EXISTS expenses CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS promotions CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS units CASCADE;


-- 1. СПРАВОЧНИКИ ГЕОГРАФИИ И ТОВАРОВ


CREATE TABLE units
(
    unit_id    SERIAL PRIMARY KEY,
    unit_name  VARCHAR(20) NOT NULL UNIQUE,
    short_name VARCHAR(10) NOT NULL
);

CREATE TABLE categories
(
    category_id        SERIAL PRIMARY KEY,
    category_name      VARCHAR(100) NOT NULL,
    parent_category_id INT REFERENCES categories (category_id)
);


CREATE TABLE stores
(
    store_id   SERIAL PRIMARY KEY,
    store_name VARCHAR(100) NOT NULL,
    city       VARCHAR(50),
    address    TEXT
);

-- 2. ПЕРСОНАЛ И КЛИЕНТЫ

CREATE TABLE positions
(
    position_id SERIAL PRIMARY KEY,
    title       VARCHAR(100) NOT NULL,
    base_salary NUMERIC(12, 2)
);

CREATE TABLE employees
(
    employee_id SERIAL PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    position_id INT REFERENCES positions (position_id),
    store_id    INT REFERENCES stores (store_id),
    hire_date   DATE DEFAULT CURRENT_DATE,
    salary      NUMERIC(12, 2)
);


-- 3. ТОВАРЫ И ПРОДАЖИ


CREATE TABLE products
(
    product_id     SERIAL PRIMARY KEY,
    sku            VARCHAR(50) UNIQUE NOT NULL,
    product_name   VARCHAR(255)       NOT NULL,
    category_id    INT REFERENCES categories (category_id),
    unit_id        INT REFERENCES units (unit_id),
    purchase_price NUMERIC(12, 2)     NOT NULL, -- Закупка
    retail_price   NUMERIC(12, 2)     NOT NULL, -- Розница
    stock_quantity NUMERIC(12, 3) DEFAULT 0
);

CREATE TABLE promotions
(
    promo_id      SERIAL PRIMARY KEY,
    promo_name    VARCHAR(255),
    discount_rate NUMERIC(5, 2),
    start_date    DATE,
    end_date      DATE
);

CREATE TABLE orders
(
    order_id         SERIAL PRIMARY KEY,
    order_timestamp  TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    employee_id      INT REFERENCES employees (employee_id),
    store_id         INT REFERENCES stores (store_id),
    total_amount_net NUMERIC(12, 2) DEFAULT 0,
    payment_method   VARCHAR(20) CHECK (payment_method IN ('cash', 'card', 'qr'))
);

CREATE TABLE order_items
(
    item_id    SERIAL PRIMARY KEY,
    order_id   INT REFERENCES orders (order_id) ON DELETE CASCADE,
    product_id INT REFERENCES products (product_id),
    quantity   NUMERIC(12, 3) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL, -- Цена на момент продажи
    promo_id   INT REFERENCES promotions (promo_id)
);


-- 4. ФИНАНСЫ И ПОТЕРЬ (KPI БЛОК)


CREATE TABLE expenses
(
    expense_id   SERIAL PRIMARY KEY,
    store_id     INT REFERENCES stores (store_id),
    expense_date DATE DEFAULT CURRENT_DATE,
    expense_type VARCHAR(100), -- 'Аренда', 'Зарплаты', 'Маркетинг'
    amount       NUMERIC(12, 2) NOT NULL
);

CREATE TABLE write_offs
(
    write_off_id   SERIAL PRIMARY KEY,
    product_id     INT REFERENCES products (product_id),
    store_id       INT REFERENCES stores (store_id),
    quantity       NUMERIC(12, 3) NOT NULL,
    reason         VARCHAR(100), -- 'Истек срок', 'Брак'
    write_off_date DATE DEFAULT CURRENT_DATE
);


-- 5. ЗАПОЛНЕНИЕ ДАННЫМИ (DML)


INSERT INTO units (unit_name, short_name)
VALUES ('Килограмм', 'кг'),
       ('Штука', 'шт');
INSERT INTO categories (category_name)
VALUES ('Фрукты'),
       ('Молочные продукты');
INSERT INTO stores (store_name, city, address)
VALUES ('Globus Center', 'Бишкек', 'Чуй 100'),
       ('Globus South', 'Ош', 'Ленина 50');
INSERT INTO positions (title)
VALUES ('Кассир'),
       ('Управляющий');

INSERT INTO products (sku, product_name, category_id, unit_id, purchase_price, retail_price, stock_quantity)
VALUES ('SKU001', 'Яблоки', 1, 1, 80.00, 120.00, 500),
       ('SKU002', 'Молоко', 2, 2, 50.00, 75.00, 200);

INSERT INTO employees (full_name, position_id, store_id, salary)
VALUES ('Иван Иванов', 1, 1, 35000),
       ('Эрмек А.', 1, 2, 30000);

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
VALUES (1, 1, 2, 120.00),
       (1, 2, 1, 75.00);

INSERT INTO expenses (store_id, expense_type, amount)
VALUES (1, 'Аренда', 50000),
       (1, 'Зарплаты', 100000);


-- 6. АНАЛИТИКА (KPI)


-- KPI 1: Чистая прибыль по филиалам (Выручка - Себестоимость - Расходы)
CREATE OR REPLACE VIEW view_simple_kpi AS
SELECT
    s.store_id,
    s.store_name,

    -- Выручка: только те заказы, которые были сделаны в этом месяце
    ROUND(COALESCE(SUM(
        CASE WHEN DATE_TRUNC('month', o.order_timestamp) = DATE_TRUNC('month', CURRENT_DATE)
        THEN oi.quantity * oi.unit_price ELSE 0 END
    ), 0)::numeric, 2) as total_revenue,

    -- Себестоимость: только для товаров, проданных в этом месяце
    ROUND(COALESCE(SUM(
        CASE WHEN DATE_TRUNC('month', o.order_timestamp) = DATE_TRUNC('month', CURRENT_DATE)
        THEN oi.quantity * p.purchase_price ELSE 0 END
    ), 0)::numeric, 2) as total_cost,

    -- Расходы: только те, что относятся к текущему месяцу
    ROUND(COALESCE((
        SELECT SUM(amount)
        FROM expenses
        WHERE store_id = s.store_id
          AND DATE_TRUNC('month', expense_date) = DATE_TRUNC('month', CURRENT_DATE)
    ), 0)::numeric, 2) as other_expenses

FROM stores s
LEFT JOIN orders o ON s.store_id = o.store_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
GROUP BY s.store_id, s.store_name;
-- Запуск отчета
SELECT *
FROM view_simple_kpi;