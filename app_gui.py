import tkinter as tk
from tkinter import ttk, messagebox
import threading
from main_parser_logic import parse_ads, save_to_excel
import sys

class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, message):
        self.widget.config(state="normal")
        self.widget.insert("end", message)
        self.widget.see("end")
        self.widget.config(state="disabled")

    def flush(self):
        pass



class ParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kleinanzeigen Парсер")
        self.root.geometry("550x500")

        ttk.Label(root, text="Ссылки (через запятую):").pack(pady=5)
        self.url_entry = tk.Text(root, height=4, wrap="word")
        self.url_entry.pack(pady=5, fill="x", padx=10)

        ttk.Label(root, text="Сколько страниц парсить:").pack(pady=5)
        self.pages_entry = ttk.Entry(root)
        self.pages_entry.insert(0, "2")
        self.pages_entry.pack(pady=5)

        ttk.Label(root, text="Минимальная цена (€):").pack(pady=5)
        self.price_entry = ttk.Entry(root)
        self.price_entry.insert(0, "1")
        self.price_entry.pack(pady=5)

        ttk.Label(root, text="Минимальное количество просмотров:").pack(pady=5)
        self.views_entry = ttk.Entry(root)
        self.views_entry.insert(0, "1")
        self.views_entry.pack(pady=5)

        self.start_button = ttk.Button(root, text="Начать парсинг", command=self.start_parsing)
        self.start_button.pack(pady=15)

        self.progress = ttk.Progressbar(root, mode='indeterminate')
        self.progress.pack(pady=5, fill="x", padx=10)

        self.status_label = ttk.Label(root, text="Ожидание запуска...")
        self.status_label.pack(pady=5)

        self.log_output = tk.Text(root, height=10, state="disabled", bg="#f8f8f8")
        self.log_output.pack(padx=10, pady=10, fill="both", expand=True)
        sys.stdout = TextRedirector(self.log_output)
        sys.stderr = TextRedirector(self.log_output)

    def start_parsing(self):
        self.start_button.config(state="disabled")
        self.progress.start()
        self.status_label.config(text="Парсинг выполняется...")
        self.clear_log()
        thread = threading.Thread(target=self.run_parser)
        thread.start()

    def run_parser(self):
        try:
            raw_urls = self.url_entry.get("1.0", "end").strip()
            urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
            if not urls:
                raise ValueError("Ссылки не указаны")

            max_pages = int(self.pages_entry.get())
            min_price = int(self.price_entry.get())
            min_views = int(self.views_entry.get())

            self.log("Парсинг начался...")
            results = list(parse_ads(urls, min_price=min_price, min_views=min_views, max_pages=max_pages))
            save_to_excel(results)
            self.log("Готово")
            self.status_label.config(text="Готово")
            messagebox.showinfo("Готово", "Парсинг завершен!")

        except Exception as e:
            self.log(f"[Ошибка] {str(e)}")
            self.status_label.config(text="Ошибка!")
            messagebox.showerror("Ошибка", str(e))
        finally:
            self.start_button.config(state="normal")
            self.progress.stop()

    def log(self, text):
        self.log_output.config(state="normal")
        self.log_output.insert("end", text + "\n")
        self.log_output.see("end")
        self.log_output.config(state="disabled")

    def clear_log(self):
        self.log_output.config(state="normal")
        self.log_output.delete("1.0", "end")
        self.log_output.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = ParserApp(root)
    root.mainloop()
