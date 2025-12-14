import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import psycopg2
from psycopg2 import sql
from datetime import datetime
import pandas as pd
from tkcalendar import DateEntry
import sys
import traceback


class DogBreedingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Система управления питомником собак")
        self.root.geometry("1400x700")

        #подключение к бд
        self.db_config = {
            'host': 'localhost',
            'database': 'Pantuhina',
            'user': 'postgres',
            'password': 'postgres',
            'port': '5432'
        }

        self.current_table = None
        self.current_filter = {}
        self.sort_column = None
        self.sort_reverse = False

        self.setup_ui()
        self.connect_db()
        self.load_table_list()

    def execute_sql(self, query, params=None, fetch=True):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if fetch:
                return self.cursor.fetchall()
            else:
                self.conn.commit()
                return True

        except Exception as e:
            self.conn.rollback()  #откатить транзакцию при ошибке
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            #подробная информация об ошибке
            error_details = traceback.format_exc()
            print(f"SQL Error: {error_msg}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            print(f"Details: {error_details}")

            raise e

    #настройка граф.интерфейса
    def setup_ui(self):
        #панель навигации
        nav_frame = ttk.Frame(self.root)
        nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        #таблицы
        ttk.Label(nav_frame, text="Таблицы БД:").pack(pady=(10, 5))
        self.table_listbox = tk.Listbox(nav_frame, height=15, width=20)
        self.table_listbox.pack(pady=(0, 10))
        self.table_listbox.bind('<<ListboxSelect>>', self.on_table_select)

        #кнопки
        ttk.Button(nav_frame, text="Добавить запись",
                   command=self.add_record).pack(fill=tk.X, pady=2)
        ttk.Button(nav_frame, text="Удалить запись",
                   command=self.delete_record).pack(fill=tk.X, pady=2)
        ttk.Button(nav_frame, text="Обновить",
                   command=self.refresh_data).pack(fill=tk.X, pady=2)

        #поиск и фильтры
        ttk.Separator(nav_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(nav_frame, text="Поиск:").pack()
        self.search_var = tk.StringVar()
        search_frame = ttk.Frame(nav_frame)
        search_frame.pack(fill=tk.X, pady=2)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<Return>', lambda e: self.apply_search())

        #кнопка поиска
        ttk.Button(search_frame, text="🔍", width=3,
                   command=self.apply_search).pack(side=tk.RIGHT, padx=(2, 0))

        ttk.Button(nav_frame, text="Фильтр...",
                   command=self.open_filter_dialog).pack(fill=tk.X, pady=5)
        ttk.Button(nav_frame, text="Сбросить фильтры",
                   command=self.reset_filters).pack(fill=tk.X, pady=2)

        #отчеты
        ttk.Separator(nav_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(nav_frame, text="Отчеты:").pack()

        reports = [
            ("Пары для вязки", self.generate_breeding_report),
            ("Пары для элитной вязки", self.generate_elite_breeding_report),
            ("Собаки для службы", self.generate_service_dogs_report)
        ]

        for report_name, command in reports:
            ttk.Button(nav_frame, text=report_name,
                       command=command).pack(fill=tk.X, pady=2)

        #основная область
        main_frame = ttk.Frame(self.root)
        main_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        #таблица для отображения данных
        self.tree = ttk.Treeview(main_frame)
        self.tree.pack(fill=tk.BOTH, expand=True)

        #полоса прокрутки
        scrollbar = ttk.Scrollbar(self.tree, orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        #бар со статусом
        self.status_bar = ttk.Label(self.root, text="Готово", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    #подключение к бд
    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            self.status_bar.config(text="Подключено к БД")
            print("Успешное подключение к БД")
        except Exception as e:
            error_msg = f"Не удалось подключиться к БД: {e}"
            messagebox.showerror("Ошибка подключения", error_msg)
            print(error_msg)
            sys.exit(1)

    #загрузка таблиц бд
    def load_table_list(self):
        self.table_listbox.delete(0, tk.END)
        tables = [
            'Breeds', 'Dogs', 'Parents', 'Exhibitions',
            'Medicine_book', 'Medicine_history'
        ]
        for table in tables:
            self.table_listbox.insert(tk.END, table)

    #выбор таблицы
    def on_table_select(self, event):
        selection = self.table_listbox.curselection()
        if selection:
            self.current_table = self.table_listbox.get(selection[0])
            self.load_table_data()

    #treeview таблиц
    def load_table_data(self, custom_query=None, params=None):
        #очистка таблицы
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.current_table and not custom_query:
            return
        try:
            if custom_query:
                if isinstance(custom_query, tuple):
                    query, query_params = custom_query
                else:
                    query = custom_query
                    query_params = params or ()
            else:
                query_parts = [f"SELECT * FROM {self.current_table}"]

                if self.current_filter:
                    conditions = []
                    query_params = []
                    for column, value in self.current_filter.items():
                        if value:
                            #для разных типов данных разные операторы
                            if value.upper() in ['TRUE', 'FALSE']:
                                conditions.append(f"{column} = %s")
                                query_params.append(value.upper() == 'TRUE')
                            elif column.endswith('_id') or column.startswith('id_'):
                                #для id
                                try:
                                    int_value = int(value)
                                    conditions.append(f"{column} = %s")
                                    query_params.append(int_value)
                                except ValueError:
                                    conditions.append(f"{column}::text ILIKE %s")
                                    query_params.append(f"%{value}%")
                            elif value in ['M', 'F']:
                                #для пола
                                conditions.append(f"{column} = %s")
                                query_params.append(value)
                            elif value in ['Gold', 'Silver', 'Bronze']:
                                #для медалей
                                conditions.append(f"{column} = %s")
                                query_params.append(value)
                            else:
                                #для текстовых полей
                                conditions.append(f"{column}::text ILIKE %s")
                                query_params.append(f"%{value}%")

                    if conditions:
                        query_parts.append("WHERE " + " AND ".join(conditions))

                #сортировка
                if self.sort_column:
                    order = "DESC" if self.sort_reverse else "ASC"
                    query_parts.append(f"ORDER BY {self.sort_column} {order}")

                query = " ".join(query_parts)
                query_params = query_params if 'query_params' in locals() else ()

            print(f"Executing query: {query}")
            print(f"With params: {query_params}")

            #выполнение запроса
            rows = self.execute_sql(query, query_params)
            columns = [desc[0] for desc in self.cursor.description]

            #настройка колонок
            self.tree["columns"] = columns
            self.tree["show"] = "headings"

            for col in columns:
                self.tree.heading(col, text=col,
                                  command=lambda c=col: self.sort_by_column(c))
                self.tree.column(col, width=100, minwidth=50)

            #заполнение данными
            for row in rows:
                self.tree.insert("", tk.END, values=row)
            self.status_bar.config(
                text=f"Таблица: {self.current_table}. Записей: {len(rows)}"
            )
        except Exception as e:
            error_msg = f"Ошибка загрузки данных: {str(e)[:100]}..."
            messagebox.showerror("Ошибка загрузки", error_msg)
            print(f"Ошибка в load_table_data: {e}")

    #сортировка столбцов
    def sort_by_column(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        self.load_table_data()

    #добавить новую запись
    def add_record(self):
        if not self.current_table:
            messagebox.showwarning("Предупреждение", "Выберите таблицу")
            return

        #создание формы ввода
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Добавить запись в {self.current_table}")
        dialog.geometry("500x600")

        #для отношения 1:М (собаки и выставки)
        if self.current_table == "Dogs":
            self.create_dog_exhibition_form(dialog)
        else:
            self.create_general_form(dialog, {})

    #форма ввода данных собак и выставки
    def create_dog_exhibition_form(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        #вкладка "собака"
        dog_frame = ttk.Frame(notebook)
        notebook.add(dog_frame, text="Данные собаки")
        try:
            self.cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'dogs' 
                ORDER BY ordinal_position
            """)

            columns = self.cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить структуру таблицы: {e}")
            parent.destroy()
            return

        entries = {}
        row_idx = 0

        for col_name, data_type, is_nullable in columns:
            if col_name == 'id_dog' and 'serial' in data_type:
                continue
            ttk.Label(dog_frame, text=f"{col_name}:").grid(
                row=row_idx, column=0, sticky=tk.W, pady=5, padx=5
            )

            #виджеты для разных типов данных
            if 'date' in data_type:
                entry = DateEntry(dog_frame, date_pattern='yyyy-mm-dd')
            elif 'bool' in data_type:
                entry = ttk.Combobox(dog_frame, values=['TRUE', 'FALSE'], state='readonly')
                entry.set('TRUE')
            elif col_name == 'gender':
                entry = ttk.Combobox(dog_frame, values=['M', 'F'], state='readonly')
                entry.set('M')
            elif col_name == 'alive':
                entry = ttk.Combobox(dog_frame, values=['TRUE', 'FALSE'], state='readonly')
                entry.set('TRUE')
            elif col_name == 'id_breed':
                # Загружаем список пород для выбора
                self.cursor.execute("SELECT id_breed, name FROM Breeds ORDER BY name")
                breeds = self.cursor.fetchall()
                breed_dict = {f"{name} (ID: {id_})": id_ for id_, name in breeds}
                entry = ttk.Combobox(dog_frame, values=list(breed_dict.keys()), state='readonly')
            else:
                entry = ttk.Entry(dog_frame)

            entry.grid(row=row_idx, column=1, sticky=tk.EW, pady=5, padx=5)
            entries[col_name] = entry
            row_idx += 1

        dog_frame.columnconfigure(1, weight=1)

        #вкладка "выставка"
        exhibition_frame = ttk.Frame(notebook)
        notebook.add(exhibition_frame, text="Выставка (опционально)")

        exp_fields = [
            ("date_exhibition", "Дата выставки:", True),
            ("mark", "Оценка (1-12):", True),
            ("medal", "Медаль:", False),
            ("name", "Название выставки:", True)
        ]

        exp_entries = {}
        for i, (field, label, required) in enumerate(exp_fields):
            ttk.Label(exhibition_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5, padx=5)

            if field == "date_exhibition":
                entry = DateEntry(exhibition_frame, date_pattern='yyyy-mm-dd')
            elif field == "medal":
                entry = ttk.Combobox(exhibition_frame,
                                     values=['', 'Gold', 'Silver', 'Bronze'],
                                     state='readonly')
                entry.set('')
            else:
                entry = ttk.Entry(exhibition_frame)

            entry.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=5)
            exp_entries[field] = (entry, required)

        exhibition_frame.columnconfigure(1, weight=1)

        #кнопки сохранения
        def save_all():
            try:
                #сохранение собаки
                dog_values = {}
                for col_name, widget in entries.items():
                    val = widget.get()

                    #обработка специальных полей
                    if col_name == 'id_breed' and isinstance(widget, ttk.Combobox):
                        selected = val
                        if selected:
                            for key, breed_id in breed_dict.items():
                                if key == selected:
                                    dog_values[col_name] = breed_id
                                    break
                    elif val:
                        #преобразование булевых значений
                        if val.upper() in ['TRUE', 'FALSE']:
                            dog_values[col_name] = val.upper() == 'TRUE'
                        else:
                            dog_values[col_name] = val

                #проверка обязательных полей
                required_fields = ['id_breed', 'owner', 'assesment', 'gender']
                for field in required_fields:
                    if field not in dog_values or dog_values[field] == '':
                        messagebox.showerror("Ошибка", f"Поле '{field}' обязательно для заполнения")
                        return
                dog_query = sql.SQL("INSERT INTO Dogs ({}) VALUES ({}) RETURNING id_dog").format(
                    sql.SQL(', ').join(map(sql.Identifier, dog_values.keys())),
                    sql.SQL(', ').join(sql.Placeholder() * len(dog_values))
                )

                print(f"Dogs query: {dog_query.as_string(self.conn)}")
                print(f"Dogs values: {list(dog_values.values())}")

                self.cursor.execute(dog_query, list(dog_values.values()))
                result = self.cursor.fetchone()
                dog_id = result[0] if result else None

                print(f"New dog ID: {dog_id}")

                #сохранение выставки
                exp_filled = False
                for field, (widget, required) in exp_entries.items():
                    if required and widget.get():
                        exp_filled = True
                        break
                if dog_id and exp_filled:
                    exp_values = {}
                    for field, (widget, required) in exp_entries.items():
                        val = widget.get()
                        if val or (required and val == ''):
                            exp_values[field] = val
                    if exp_values:
                        exp_values['id_dog'] = dog_id
                        exp_query = sql.SQL("INSERT INTO Exhibitions ({}) VALUES ({})").format(
                            sql.SQL(', ').join(map(sql.Identifier, exp_values.keys())),
                            sql.SQL(', ').join(sql.Placeholder() * len(exp_values))
                        )
                        print(f"Exhibitions query: {exp_query.as_string(self.conn)}")
                        print(f"Exhibitions values: {list(exp_values.values())}")
                        self.cursor.execute(exp_query, list(exp_values.values()))
                self.conn.commit()
                messagebox.showinfo("Успех", "Данные сохранены")
                parent.destroy()
                self.refresh_data()

            except Exception as e:
                self.conn.rollback()
                error_msg = f"Ошибка сохранения: {str(e)[:200]}..."
                messagebox.showerror("Ошибка", error_msg)
                print(f"Ошибка в save_all: {e}")
                traceback.print_exc()

        ttk.Button(parent, text="Сохранить все", command=save_all).pack(pady=10)

    #общие формы таблиц
    def create_general_form(self, parent, default_values):
        #получение структуры таблицы
        try:
            self.cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position
            """, (self.current_table.lower(),))

            columns = self.cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить структуру таблицы: {e}")
            parent.destroy()
            return

        entries = {}
        for i, (col_name, data_type, is_nullable) in enumerate(columns):
            if 'serial' in data_type or col_name in ['id_dog', 'id_exhibition', 'id_record', 'id_illness']:
                continue

            ttk.Label(parent, text=f"{col_name}:").grid(
                row=i, column=0, sticky=tk.W, pady=5, padx=5
            )

            #специальные виджеты для разных типов данных
            if 'date' in data_type:
                entry = DateEntry(parent, date_pattern='yyyy-mm-dd')
            elif 'bool' in data_type:
                entry = ttk.Combobox(parent, values=['TRUE', 'FALSE'], state='readonly')
                entry.set('TRUE')
            elif col_name == 'gender':
                entry = ttk.Combobox(parent, values=['M', 'F'], state='readonly')
                entry.set('M')
            elif col_name == 'medal':
                entry = ttk.Combobox(parent,
                                     values=['', 'Gold', 'Silver', 'Bronze'],
                                     state='readonly')
                entry.set('')
            elif col_name == 'id_breed':
                #загружаем список пород для выбора
                self.cursor.execute("SELECT id_breed, name FROM Breeds ORDER BY name")
                breeds = self.cursor.fetchall()
                breed_dict = {f"{name} (ID: {id_})": id_ for id_, name in breeds}
                entry = ttk.Combobox(parent, values=list(breed_dict.keys()), state='readonly')
            elif col_name in ['id_mother', 'id_father', 'id_dog']:
                #загружаем список собак для выбора
                self.cursor.execute("SELECT id_dog, owner FROM Dogs WHERE alive = TRUE ORDER BY owner")
                dogs = self.cursor.fetchall()
                dog_dict = {f"{owner} (ID: {id_})": id_ for id_, owner in dogs}
                entry = ttk.Combobox(parent, values=[''] + list(dog_dict.keys()), state='readonly')
                entry.set('')
            elif col_name == 'id_illness':
                #загружаем список болезней для выбора
                self.cursor.execute("SELECT id_illness, name FROM Medicine_book ORDER BY name")
                illnesses = self.cursor.fetchall()
                illness_dict = {f"{name} (ID: {id_})": id_ for id_, name in illnesses}
                entry = ttk.Combobox(parent, values=list(illness_dict.keys()), state='readonly')
            else:
                entry = ttk.Entry(parent)

            entry.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=5)
            entries[col_name] = (
            entry, data_type, col_name in ['id_breed', 'id_mother', 'id_father', 'id_dog', 'id_illness'])

        parent.columnconfigure(1, weight=1)

        def save_record():
            try:
                values = {}
                special_dicts = {}

                for col_name, (widget, data_type, is_special) in entries.items():
                    val = widget.get()

                    if val:
                        #обработка специальных полей с выпадающими списками
                        if is_special and isinstance(widget, ttk.Combobox):
                            if col_name == 'id_breed':
                                self.cursor.execute("SELECT id_breed, name FROM Breeds ORDER BY name")
                                items = self.cursor.fetchall()
                                item_dict = {f"{name} (ID: {id_})": id_ for id_, name in items}
                            elif col_name in ['id_mother', 'id_father', 'id_dog']:
                                self.cursor.execute("SELECT id_dog, owner FROM Dogs WHERE alive = TRUE ORDER BY owner")
                                items = self.cursor.fetchall()
                                item_dict = {f"{owner} (ID: {id_})": id_ for id_, owner in items}
                            elif col_name == 'id_illness':
                                self.cursor.execute("SELECT id_illness, name FROM Medicine_book ORDER BY name")
                                items = self.cursor.fetchall()
                                item_dict = {f"{name} (ID: {id_})": id_ for id_, name in items}
                            else:
                                item_dict = {}

                            #извлекаем ключ из строки
                            for key, item_id in item_dict.items():
                                if key == val:
                                    values[col_name] = item_id
                                    break

                        #преобразование булевых значений
                        elif val.upper() in ['TRUE', 'FALSE']:
                            values[col_name] = val.upper() == 'TRUE'
                        elif 'int' in data_type or 'numeric' in data_type:
                            try:
                                values[col_name] = int(val)
                            except ValueError:
                                try:
                                    values[col_name] = float(val)
                                except ValueError:
                                    values[col_name] = val
                        else:
                            values[col_name] = val

                if values:
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(self.current_table),
                        sql.SQL(', ').join(map(sql.Identifier, values.keys())),
                        sql.SQL(', ').join(sql.Placeholder() * len(values))
                    )

                    print(f"Insert query: {query.as_string(self.conn)}")
                    print(f"Values: {list(values.values())}")

                    self.cursor.execute(query, list(values.values()))
                    self.conn.commit()
                    messagebox.showinfo("Успех", "Запись добавлена")
                    parent.destroy()
                    self.refresh_data()

            except Exception as e:
                self.conn.rollback()
                error_msg = f"Ошибка: {str(e)[:200]}..."
                messagebox.showerror("Ошибка", error_msg)
                print(f"Ошибка в save_record: {e}")
                traceback.print_exc()

        ttk.Button(parent, text="Сохранить", command=save_record).pack(pady=10)

    #удаление выбранной записи
    def delete_record(self):
        if not self.current_table:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите запись для удаления")
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранную запись?"):
            try:
                #получение первичного ключа
                item = self.tree.item(selection[0])
                record_id = item['values'][0]
                #получаем имя первичного ключа
                self.cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.key_column_usage 
                    WHERE table_name = %s 
                    AND constraint_name LIKE '%_pkey'
                """, (self.current_table.lower(),))

                pk_result = self.cursor.fetchone()
                pk_column = pk_result[0] if pk_result else 'id'

                query = f"DELETE FROM {self.current_table} WHERE {pk_column} = %s"
                self.cursor.execute(query, (record_id,))
                self.conn.commit()

                self.tree.delete(selection[0])
                self.status_bar.config(text="Запись удалена")

            except Exception as e:
                self.conn.rollback()
                error_msg = f"Ошибка удаления: {str(e)[:100]}..."
                messagebox.showerror("Ошибка", error_msg)
                print(f"Ошибка в delete_record: {e}")

    #использование поиска
    def apply_search(self):
        search_text = self.search_var.get()
        if search_text and self.current_table:
            try:
                #поиск по всем текстовым полям
                self.cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    AND data_type IN ('text', 'character varying', 'char')
                """, (self.current_table.lower(),))

                text_columns = [row[0] for row in self.cursor.fetchall()]

                if text_columns:
                    conditions = [f"{col}::text ILIKE %s" for col in text_columns]
                    query = f"""
                        SELECT * FROM {self.current_table} 
                        WHERE {' OR '.join(conditions)}
                    """
                    params = [f"%{search_text}%"] * len(text_columns)

                    self.load_table_data(custom_query=(query, params))
            except Exception as e:
                messagebox.showerror("Ошибка поиска", f"Ошибка: {e}")
        else:
            self.load_table_data()

    #диалог фильтра
    def open_filter_dialog(self):
        if not self.current_table:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Фильтр: {self.current_table}")
        dialog.geometry("500x400")

        try:
            self.cursor.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (self.current_table.lower(),))

            columns = self.cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить структуру таблицы: {e}")
            dialog.destroy()
            return
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        filter_widgets = {}
        for i, (col_name, data_type) in enumerate(columns):
            ttk.Label(scrollable_frame, text=f"{col_name}:").grid(
                row=i, column=0, sticky=tk.W, pady=5, padx=5
            )

            #виджеты для разных типов данных
            if 'bool' in data_type:
                widget = ttk.Combobox(scrollable_frame, values=['', 'TRUE', 'FALSE'],
                                      state='readonly')
                widget.set('')
            elif col_name in ['gender', 'medal']:
                values = {'gender': ['', 'M', 'F'],
                          'medal': ['', 'Gold', 'Silver', 'Bronze']}
                widget = ttk.Combobox(scrollable_frame, values=values.get(col_name, ['']),
                                      state='readonly')
                widget.set('')
            elif 'int' in data_type or 'numeric' in data_type or 'serial' in data_type:
                #для числовых полей используем Entry
                widget = ttk.Entry(scrollable_frame)
            elif 'date' in data_type:
                #для дат используем DateEntry
                widget = DateEntry(scrollable_frame, date_pattern='yyyy-mm-dd')
            else:
                #для текстовых полей
                widget = ttk.Entry(scrollable_frame)

            widget.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=5)
            filter_widgets[col_name] = (widget, data_type)

        scrollable_frame.columnconfigure(1, weight=1)

        #кнопки внизу диалога
        button_frame = ttk.Frame(dialog)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        def apply_filters():
            filters = {}
            for col_name, (widget, data_type) in filter_widgets.items():
                value = None

                if isinstance(widget, ttk.Combobox):
                    value = widget.get()
                elif isinstance(widget, DateEntry):
                    value = widget.get_date().strftime('%Y-%m-%d') if widget.get_date() else ''
                elif isinstance(widget, ttk.Entry):
                    value = widget.get()

                if value and value != '':
                    #преобразуем значение в зависимости от типа данных
                    if data_type == 'date' and isinstance(value, str):
                        try:
                            datetime.strptime(value, '%Y-%m-%d')
                            filters[col_name] = value
                        except ValueError:
                            messagebox.showwarning("Предупреждение",
                                                   f"Некорректная дата в поле {col_name}. Используйте формат ГГГГ-ММ-ДД")
                            return
                    elif 'bool' in data_type:
                        filters[col_name] = value
                    elif col_name in ['gender', 'medal']:
                        filters[col_name] = value
                    elif ('int' in data_type or 'numeric' in data_type or 'serial' in data_type) and value:
                        #проверяем, что это число
                        try:
                            float(value)  #проверяем, можно ли преобразовать в число
                            filters[col_name] = value
                        except ValueError:
                            messagebox.showwarning("Предупреждение",
                                                   f"Некорректное число в поле {col_name}")
                            return
                    else:
                        filters[col_name] = value

            self.current_filter = filters
            self.load_table_data()
            dialog.destroy()
            messagebox.showinfo("Фильтр", f"Применено {len(filters)} фильтров")

        def clear_filters():
            for col_name, (widget, data_type) in filter_widgets.items():
                if isinstance(widget, ttk.Combobox):
                    widget.set('')
                elif isinstance(widget, DateEntry):
                    widget.set_date(None)
                elif isinstance(widget, ttk.Entry):
                    widget.delete(0, tk.END)

        ttk.Button(button_frame, text="Применить фильтры",
                   command=apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Очистить поля",
                   command=clear_filters).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Отмена",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=2)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    #сброс фильтров
    def reset_filters(self):
        self.current_filter = {}
        self.sort_column = None
        self.sort_reverse = False
        self.search_var.set("")
        self.load_table_data()
        messagebox.showinfo("Фильтры", "Все фильтры сброшены")

    #обновление данных таблицы
    def refresh_data(self):
        if self.current_table:
            self.load_table_data()

    #отчет пар для вязки
    def generate_breeding_report(self):
        base_query = """
        SELECT 
            m.id_dog as id_кобеля,
            f.id_dog as id_суки,
            m.owner as владелец_кобеля,
            f.owner as владелец_суки,
            bm.name as порода_кобеля,
            bf.name as порода_суки,
            m.assesment as оценка_кобеля,
            f.assesment as оценка_суки,
            (m.assesment + f.assesment) as сумма_оценок
        FROM Dogs m
        JOIN Dogs f ON m.id_breed = f.id_breed 
            AND m.gender = 'M' 
            AND f.gender = 'F'
            AND m.id_dog != f.id_dog
        JOIN Breeds bm ON m.id_breed = bm.id_breed
        JOIN Breeds bf ON f.id_breed = bf.id_breed
        WHERE m.alive = TRUE AND f.alive = TRUE
            AND m.assesment >= 4 AND f.assesment >= 4
        """

        self.show_report_dialog(
            title="Пары для вязки",
            description="Критерии отбора:\n• Оценка родителей ≥ 4\n• Отсутствие родственных связей\n• Все оценки на выставках ≥ 4",
            base_query=base_query,
            report_type="breeding"
        )

    #отчет пар для элитной вязки
    def generate_elite_breeding_report(self):
        base_query = """
        SELECT 
            m.id_dog as id_кобеля,
            f.id_dog as id_суки,
            m.owner as владелец_кобеля,
            f.owner as владелец_суки,
            bm.name as порода_кобеля,
            bf.name as порода_суки,
            m.assesment as оценка_кобеля,
            f.assesment as оценка_суки,
            (SELECT COUNT(*) FROM Exhibitions WHERE id_dog = m.id_dog AND medal IS NOT NULL) as медали_кобеля,
            (SELECT COUNT(*) FROM Exhibitions WHERE id_dog = f.id_dog AND medal IS NOT NULL) as медали_суки,
            (m.assesment + f.assesment) as сумма_оценок
        FROM Dogs m
        JOIN Dogs f ON m.id_breed = f.id_breed 
            AND m.gender = 'M' 
            AND f.gender = 'F'
            AND m.id_dog != f.id_dog
        JOIN Breeds bm ON m.id_breed = bm.id_breed
        JOIN Breeds bf ON f.id_breed = bf.id_breed
        WHERE m.alive = TRUE AND f.alive = TRUE
            AND m.assesment >= 4 AND f.assesment >= 4
            AND EXISTS (SELECT 1 FROM Exhibitions WHERE id_dog = m.id_dog AND medal IS NOT NULL)
            AND EXISTS (SELECT 1 FROM Exhibitions WHERE id_dog = f.id_dog AND medal IS NOT NULL)
        """

        self.show_report_dialog(
            title="Пары для элитной вязки",
            description="Критерии отбора:\n• Оценка родителей ≥ 4\n• Наличие минимум 1 медали у каждого родителя\n• Обязательно наличие щенков",
            base_query=base_query,
            report_type="elite"
        )

    #отчет слежубных собак
    def generate_service_dogs_report(self):
        base_query = """
        SELECT 
            d.id_dog as id_собаки,
            d.owner as владелец,
            d.assesment as оценка,
            d.psyche_test as тест_психики,
            b.name as порода,
            b.characteristic as характеристика
        FROM Dogs d
        JOIN Breeds b ON d.id_breed = b.id_breed
        WHERE d.alive = TRUE
            AND d.psyche_test = 5
        """

        self.show_report_dialog(
            title="Собаки для служебного использования",
            description="Критерии отбора:\n• Тест психики = 5\n• Живые собаки",
            base_query=base_query,
            report_type="service"
        )

    #окно с выбором сортировки отчета
    def show_report_dialog(self, title, description, base_query, report_type):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Отчет: {title}")
        dialog.geometry("600x300")
        desc_frame = ttk.Frame(dialog)
        desc_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(desc_frame, text=title,
                  font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        desc_text = tk.Text(desc_frame, height=4, width=60, wrap=tk.WORD)
        desc_text.insert(1.0, description)
        desc_text.config(state='disabled')
        desc_text.pack(fill=tk.X, pady=5)

        ttk.Separator(dialog, orient='horizontal').pack(fill=tk.X, padx=10)
        sort_frame = ttk.Frame(dialog)
        sort_frame.pack(pady=15, padx=20)

        ttk.Label(sort_frame, text="Сортировка:",
                  font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        sort_options = []
        if report_type == "breeding":
            sort_options = [
                ("По сумме оценок", "сумма_оценок"),
                ("По оценке кобеля", "оценка_кобеля"),
                ("По оценке суки", "оценка_суки"),
                ("По породе кобеля", "порода_кобеля"),
                ("По породе суки", "порода_суки")
            ]
        elif report_type == "elite":
            sort_options = [
                ("По сумме оценок", "сумма_оценок"),
                ("По оценке кобеля", "оценка_кобеля"),
                ("По оценке суки", "оценка_суки"),
                ("По медалям кобеля", "медали_кобеля"),
                ("По медалям суки", "медали_суки")
            ]
        elif report_type == "service":
            sort_options = [
                ("По оценке собаки", "оценка"),
                ("По тесту психики", "тест_психики"),
                ("По породе", "порода"),
                ("По владельцу", "владелец")
            ]

        sort_var = tk.StringVar()
        sort_combo = ttk.Combobox(sort_frame, textvariable=sort_var,
                                  values=[opt[0] for opt in sort_options],
                                  state='readonly', width=30)
        sort_combo.grid(row=0, column=1, sticky=tk.EW, padx=5)
        sort_combo.set(sort_options[0][0])

        ttk.Label(sort_frame, text="Порядок:").grid(row=1, column=0, sticky=tk.W, pady=5)

        order_var = tk.StringVar(value="По убыванию")
        order_combo = ttk.Combobox(sort_frame, textvariable=order_var,
                                   values=["По возрастанию", "По убыванию"],
                                   state='readonly', width=30)
        order_combo.grid(row=1, column=1, sticky=tk.EW, padx=5)

        sort_frame.columnconfigure(1, weight=1)

        def generate_report():
            try:
                #SQL выражение для сортировки
                selected_text = sort_var.get()
                selected_field = None
                for text, field in sort_options:
                    if text == selected_text:
                        selected_field = field
                        break

                if not selected_field:
                    selected_field = sort_options[0][1]
                order = "DESC" if order_var.get() == "По убыванию" else "ASC"

                #формируем финальный запрос с сортировкой
                final_query = base_query + f" ORDER BY {selected_field} {order}"
                rows = self.execute_sql(final_query)
                columns = [desc[0] for desc in self.cursor.description]

                dialog.destroy()
                self.show_report_results(title, columns, rows, report_type)

            except Exception as e:
                error_msg = f"Ошибка генерации отчета: {str(e)[:100]}..."
                messagebox.showerror("Ошибка", error_msg)
                print(f"Ошибка в generate_report: {e}")
                print(f"Query: {final_query if 'final_query' in locals() else base_query}")

        def cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Сгенерировать отчет",
                   command=generate_report, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена",
                   command=cancel, width=10).pack(side=tk.RIGHT, padx=5)

    #отображение результатов отчета
    def show_report_results(self, title, columns, data, report_type=None):
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Результаты: {title}")
        report_window.geometry("1200x700")
        header_frame = ttk.Frame(report_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=title,
                  font=('Arial', 14, 'bold')).pack()

        ttk.Label(header_frame, text=f"Найдено записей: {len(data)}",
                  font=('Arial', 10)).pack(pady=5)
        tree_frame = ttk.Frame(report_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        #создаем Treeview с полосами прокрутки
        tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree["columns"] = columns

        for col in columns:
            tree.heading(col, text=col, anchor=tk.W)
            tree.column(col, width=120, minwidth=80, anchor=tk.W)

        #заполнение данными
        for row in data:
            tree.insert("", tk.END, values=row)

        #статистика и кнопки экспорта
        bottom_frame = ttk.Frame(report_window)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        #статистика
        stats_text = f"Всего записей: {len(data)}"
        ttk.Label(bottom_frame, text=stats_text).pack(side=tk.LEFT)

        #кнопки
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(side=tk.RIGHT)

        #экспорт в csv
        def export_to_csv():
            try:
                df = pd.DataFrame(data, columns=columns)
                filename = f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                messagebox.showinfo("Экспорт", f"Данные сохранены в {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка экспорта", str(e))

        ttk.Button(button_frame, text="📥 Экспорт в CSV",
                   command=export_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Закрыть",
                   command=report_window.destroy).pack(side=tk.LEFT, padx=5)

    def __del__(self):
        #закрытие подключения к бд при завершении работы
        if hasattr(self, 'conn'):
            self.cursor.close()
            self.conn.close()


def main():
    root = tk.Tk()
    app = DogBreedingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()