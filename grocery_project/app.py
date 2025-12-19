from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_db_connection, execute_query
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'grocery_secret_key'


# --- 1. ВИТРИНА ---
@app.route('/')
def shop():
    search = request.args.get('search', '')
    cat_id = request.args.get('cat_id', '')

    query = "SELECT p.*, c.category_name FROM products p LEFT JOIN categories c ON p.category_id = c.category_id WHERE p.stock_quantity > 0"
    params = []

    if search:
        query += " AND p.product_name ILIKE %s"
        params.append(f'%{search}%')
    if cat_id:
        query += " AND p.category_id = %s"
        params.append(cat_id)

    products = execute_query(query, params, fetch=True)
    categories = execute_query("SELECT * FROM categories", fetch=True)
    return render_template('shop.html', products=products, categories=categories)

# --- 2. ДАШБОРД (KPI) ---
@app.route('/dashboard')
def dashboard():
    # 1. Данные из SQL View (Выручка и Чистая прибыль по филиалам)
    stats = execute_query("SELECT * FROM view_simple_kpi", fetch=True)

    # 2. Товары с низким остатком (KPI по складу)
    products_low = execute_query("SELECT * FROM products WHERE stock_quantity < 10 ORDER BY stock_quantity ASC",
                                 fetch=True)

    # 3. Общие итоги для карточек сверху
    totals = execute_query("""
                           SELECT SUM(revenue) as total_rev, SUM(net_profit) as total_profit
                           FROM view_sales_analysis
                           """, fetch=True)

    return render_template('dashboard.html', stats=stats)

# --- 3. АДМИНКА (Обновленная) ---
@app.route('/admin', methods=['GET', 'POST'])  # Обязательно добавьте методы!
def admin():
    if request.method == 'POST':
        # Этот блок сработает, когда вы нажмете кнопку "Добавить"
        data = (
            request.form['sku'],
            request.form['name'],
            request.form['category_id'],
            request.form['unit_id'],
            request.form['purchase_price'],
            request.form['retail_price'],
            request.form['stock']
        )
        query = """
                INSERT INTO products (sku, product_name, category_id, unit_id, purchase_price, retail_price, stock_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s) \
                """
        execute_query(query, data)
        flash('Товар успешно добавлен!')
        return redirect(url_for('admin'))  # Перезагружаем страницу после сохранения

    # Этот блок сработает просто при открытии страницы (GET)
    categories = execute_query("SELECT * FROM categories", fetch=True)
    units = execute_query("SELECT * FROM units", fetch=True)

    # Убедитесь, что здесь есть p.stock_quantity
    products = execute_query("""
                             SELECT p.product_id,
                                    p.sku,
                                    p.product_name,
                                    p.purchase_price,
                                    p.retail_price,
                                    p.stock_quantity,
                                    c.category_name,
                                    u.short_name
                             FROM products p
                                      LEFT JOIN categories c ON p.category_id = c.category_id
                                      LEFT JOIN units u ON p.unit_id = u.unit_id
                             ORDER BY p.product_id DESC
                             """, fetch=True)

    return render_template('admin.html', categories=categories, units=units, products=products)


# --- 4. ОФОРМЛЕНИЕ ЗАКАЗА ---
@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Ваша корзина пуста!')
        return redirect(url_for('shop'))

    # 1. Получаем ID текущего филиала из сессии (если нет, то 1 по умолчанию)
    current_store_id = session.get('store_id', 1)

    # 2. Получаем данные из формы корзины
    employee_id = request.form.get('employee_id')
    customer_id = request.form.get('customer_id')

    # Если клиент не выбран (пустая строка), заменяем на None для SQL NULL
    if not customer_id: customer_id = None

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 3. Создаем запись в таблице orders с учетом выбранного магазина
        cur.execute("""
                    INSERT INTO orders (store_id, employee_id, customer_id, total_amount_net, payment_method)
                    VALUES (%s, %s, %s, 0, 'card') RETURNING order_id
                    """, (current_store_id, employee_id, customer_id))

        order_id = cur.fetchone()['order_id']

        total = 0
        # 4. Обработка товаров в корзине
        for p_id, qty in cart.items():
            cur.execute("SELECT retail_price, stock_quantity FROM products WHERE product_id = %s", (p_id,))
            p = cur.fetchone()

            if not p: continue

            # Проверка остатка перед продажей
            if p['stock_quantity'] < qty:
                raise Exception(f"Недостаточно товара на складе (ID: {p_id})")

            # Добавляем позицию в чек (order_items)
            cur.execute("""
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                        VALUES (%s, %s, %s, %s)
                        """, (order_id, p_id, qty, p['retail_price']))

            # Списываем товар со склада
            cur.execute("UPDATE products SET stock_quantity = stock_quantity - %s WHERE product_id = %s", (qty, p_id))

            total += p['retail_price'] * qty

        # 5. Обновляем итоговую сумму в заказе
        cur.execute("UPDATE orders SET total_amount_net = %s WHERE order_id = %s", (total, order_id))

        conn.commit()
        session.pop('cart')  # Очищаем корзину после успеха
        flash(f'Заказ №{order_id} на сумму {total} сом успешно оформлен!')

    except Exception as e:
        conn.rollback()  # Отменяем всё, если произошла ошибка (например, не хватило товара)
        flash(f'Ошибка при оформлении: {e}')
    finally:
        conn.close()

    return redirect(url_for('shop'))

@app.context_processor
def inject_stores():
    stores = execute_query("SELECT * FROM stores", fetch=True)
    return dict(all_stores=stores)

# --- 5. ДОБАВЛЕНИЕ В КОРЗИНУ ---
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = {}

    p_id = str(product_id)  # ID должен быть строкой для ключа в сессии
    if p_id in session['cart']:
        session['cart'][p_id] += 1
    else:
        session['cart'][p_id] = 1

    session.modified = True
    flash('Товар добавлен в корзину!')
    return redirect(url_for('shop'))


# --- 6. ПРОСМОТР КОРЗИНЫ ---
@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    products_in_cart = []
    total_sum = 0

    if cart:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Получаем ID всех товаров в корзине
        product_ids = [int(p_id) for p_id in cart.keys()]

        # Запрос: получаем товары + их единицы измерения
        cur.execute("""
                    SELECT p.product_id, p.product_name, p.retail_price, u.short_name
                    FROM products p
                             JOIN units u ON p.unit_id = u.unit_id
                    WHERE p.product_id IN %s
                    """, (tuple(product_ids),))

        db_products = cur.fetchall()

        for p in db_products:
            qty = cart[str(p['product_id'])]
            subtotal = p['retail_price'] * qty
            total_sum += subtotal
            products_in_cart.append({
                'id': p['product_id'],
                'name': p['product_name'],
                'price': p['retail_price'],
                'unit': p['short_name'],
                'qty': qty,
                'subtotal': subtotal
            })

        # Для выбора в форме оформления:
        cur.execute("SELECT employee_id, full_name FROM employees")
        employees = cur.fetchall()

        cur.execute("SELECT customer_id, full_name FROM customers")
        customers = cur.fetchall()

        cur.close()
        conn.close()
    else:
        employees, customers = [], []

    return render_template('cart.html',
                           products=products_in_cart,
                           total=total_sum,
                           employees=employees,
                           customers=customers)


# --- 7. УДАЛЕНИЕ ИЗ КОРЗИНЫ ---
@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    p_id = str(product_id)
    if p_id in cart:
        session['cart'].pop(p_id)
        session.modified = True
        flash('Товар удален из корзины')
    return redirect(url_for('view_cart'))


# --- 8. УПРАВЛЕНИЕ РАСХОДАМИ (Аренда, ЗП и т.д.) ---
@app.route('/admin/expenses', methods=['GET', 'POST'])
def manage_expenses():
    if request.method == 'POST':
        data = (
            request.form['store_id'],
            request.form['expense_type'],
            request.form['amount']
        )
        execute_query("INSERT INTO expenses (store_id, expense_type, amount) VALUES (%s, %s, %s)", data)
        flash('Расход зафиксирован!')
        return redirect(url_for('manage_expenses'))

    stores = execute_query("SELECT * FROM stores", fetch=True)
    expenses = execute_query(
        "SELECT e.*, s.store_name FROM expenses e JOIN stores s ON e.store_id = s.store_id ORDER BY expense_date DESC",
        fetch=True)
    return render_template('expenses.html', stores=stores, expenses=expenses)


# --- 9. УЧЕТ СПИСАНИЙ (Брак, Срок годности) ---
@app.route('/admin/writeoff', methods=['GET', 'POST'])
def manage_writeoffs():
    if request.method == 'POST':
        p_id = request.form['product_id']
        qty = request.form['quantity']
        # 1. Записываем списание
        execute_query("INSERT INTO write_offs (product_id, store_id, quantity, reason) VALUES (%s, 1, %s, %s)",
                      (p_id, qty, request.form['reason']))
        # 2. Уменьшаем остаток на складе
        execute_query("UPDATE products SET stock_quantity = stock_quantity - %s WHERE product_id = %s", (qty, p_id))
        flash('Товар списан со склада')
        return redirect(url_for('manage_writeoffs'))

    products = execute_query("SELECT * FROM products", fetch=True)
    return render_template('write_offs.html', products=products)


# --- 10. КЛИЕНТЫ И ЛОЯЛЬНОСТЬ ---
@app.route('/admin/customers', methods=['GET', 'POST'])
def manage_customers():
    if request.method == 'POST':
        execute_query("INSERT INTO customers (full_name, phone) VALUES (%s, %s)",
                      (request.form['name'], request.form['phone']))
        flash('Клиент зарегистрирован!')

    customers = execute_query("SELECT * FROM customers", fetch=True)
    return render_template('customers.html', customers=customers)


@app.route('/admin/employees', methods=['GET', 'POST'])
def manage_employees():
    if request.method == 'POST':
        data = (request.form['name'], request.form['pos_id'], request.form['store_id'], request.form['salary'])
        execute_query("INSERT INTO employees (full_name, position_id, store_id, salary) VALUES (%s, %s, %s, %s)", data)
        flash('Сотрудник нанят!')

    employees = execute_query("""
                              SELECT e.*, p.title, s.store_name
                              FROM employees e
                                       JOIN positions p ON e.position_id = p.position_id
                                       JOIN stores s ON e.store_id = s.store_id
                              """, fetch=True)
    positions = execute_query("SELECT * FROM positions", fetch=True)
    stores = execute_query("SELECT * FROM stores", fetch=True)
    return render_template('employees.html', employees=employees, positions=positions, stores=stores)

@app.route('/admin/orders')
def order_history():
    # Получаем общую информацию о заказах
    orders = execute_query("""
        SELECT o.order_id, o.order_timestamp, o.total_amount_net, s.store_name, e.full_name as seller
        FROM orders o
        JOIN stores s ON o.store_id = s.store_id
        LEFT JOIN employees e ON o.employee_id = e.employee_id
        ORDER BY o.order_timestamp DESC
    """, fetch=True)
    return render_template('order_history.html', orders=orders)

@app.route('/admin/add_category', methods=['POST'])
def add_category():
    category_name = request.form.get('category_name')
    if category_name:
        execute_query("INSERT INTO categories (category_name) VALUES (%s)", (category_name,))
        flash(f'Категория "{category_name}" успешно создана!')
    return redirect(url_for('admin'))

@app.route('/admin/directories')
def directories():
    brands = execute_query("SELECT * FROM brands", fetch=True)
    suppliers = execute_query("SELECT * FROM suppliers", fetch=True)
    return render_template('directories.html', brands=brands, suppliers=suppliers)


@app.route('/set_store/<int:store_id>')
def set_store(store_id):
    # Получаем данные магазина, чтобы сохранить его название для красоты
    store = execute_query("SELECT store_name FROM stores WHERE store_id = %s", (store_id,), fetch=True)
    if store:
        session['store_id'] = store_id
        session['store_name'] = store[0]['store_name']
        flash(f'Вы переключились на филиал: {session["store_name"]}')

    # Возвращаемся на ту страницу, где были
    return redirect(request.referrer or url_for('shop'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)