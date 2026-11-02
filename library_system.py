from __future__ import annotations

import csv
import os
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


DATA_DIR = Path(__file__).resolve().parent
BOOKS_FILE = DATA_DIR / "books.csv"
MEMBERS_FILE = DATA_DIR / "members.csv"
LOANS_FILE = DATA_DIR / "loans.csv"
LIBRARIANS_FILE = DATA_DIR / "librarians.csv"

BLUE = "#0F766E"
DARK_BLUE = "#142D42"
LIGHT_BLUE = "#F1F5F9"
WHITE = "#FFFFFF"
GREEN = "#0F766E"
TEXT = "#233C50"
MUTED = "#64748B"
BORDER = "#DCE5ED"


def setup_files() -> None:
    needed = {
        BOOKS_FILE: ["book_id", "title", "author", "available"],
        MEMBERS_FILE: ["member_id", "name", "password", "active_loans"],
        LOANS_FILE: ["loan_id", "member_id", "book_id", "borrow_date", "due_date"],
        LIBRARIANS_FILE: ["librarian_id", "password"],
    }
    for path, headers in needed.items():
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as file:
                csv.writer(file).writerow(headers)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def save_csv(path: Path, headers: list[str], data: list[dict[str, object]]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    os.replace(temp_path, path)


class Book:
    def __init__(self, book_id: str, title: str, author: str, available: object = True):
        self.book_id = book_id.strip().upper()
        self.title = title.strip()
        self.author = author.strip()
        self.available = available if isinstance(available, bool) else str(available).lower() == "true"

    def to_dict(self) -> dict[str, object]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "available": self.available,
        }


class Member:
    def __init__(
        self,
        member_id: str,
        name: str,
        password: str,
        active_loans: object = "",
    ):
        self.member_id = member_id.strip().upper()
        self.name = name.strip()
        self.password = password
        if isinstance(active_loans, list):
            self.loans = list(active_loans)
        else:
            self.loans = [item for item in str(active_loans).split("|") if item]

    def to_dict(self) -> dict[str, object]:
        return {
            "member_id": self.member_id,
            "name": self.name,
            "password": self.password,
            "active_loans": "|".join(self.loans),
        }


class Loan:
    def __init__(
        self,
        loan_id: str,
        member_id: str,
        book_id: str,
        borrow_date: str | None = None,
        due_date: str | None = None,
    ):
        borrowed = date.today()
        self.loan_id = loan_id.strip().upper()
        self.member_id = member_id.strip().upper()
        self.book_id = book_id.strip().upper()
        self.borrow_date = borrow_date or borrowed.isoformat()
        self.due_date = due_date or (borrowed + timedelta(days=14)).isoformat()

    def to_dict(self) -> dict[str, object]:
        return {
            "loan_id": self.loan_id,
            "member_id": self.member_id,
            "book_id": self.book_id,
            "borrow_date": self.borrow_date,
            "due_date": self.due_date,
        }


class Library:
    def __init__(self):
        self.books: dict[str, Book] = {}
        self.members: dict[str, Member] = {}
        self.librarians: dict[str, str] = {}
        self.loans: dict[str, Loan] = {}
        self.next_loan = 1
        setup_files()
        self._load()
        self._seed_sample_data()

    def _load(self) -> None:
        for row in load_csv(BOOKS_FILE):
            book = Book(**row)
            self.books[book.book_id] = book
        for row in load_csv(MEMBERS_FILE):
            member = Member(**row)
            self.members[member.member_id] = member
        for row in load_csv(LOANS_FILE):
            loan = Loan(**row)
            self.loans[loan.loan_id] = loan
            try:
                self.next_loan = max(self.next_loan, int(loan.loan_id[1:]) + 1)
            except (ValueError, IndexError):
                pass
        for row in load_csv(LIBRARIANS_FILE):
            librarian_id = row.get("librarian_id", "").strip().upper()
            if librarian_id:
                self.librarians[librarian_id] = row.get("password", "")
        self._reconcile_active_loans()

    def _reconcile_active_loans(self) -> None:
        for book in self.books.values():
            book.available = True
        for member in self.members.values():
            member.loans = []
        for loan in self.loans.values():
            if loan.book_id in self.books:
                self.books[loan.book_id].available = False
            if loan.member_id in self.members and loan.book_id not in self.members[loan.member_id].loans:
                self.members[loan.member_id].loans.append(loan.book_id)

    def _seed_sample_data(self) -> None:
        changed = False
        if not self.librarians:
            self.librarians["LIB01"] = "admin"
            self._save_librarians()
        if not self.books:
            samples = (
                Book("B001", "Python Crash Course", "Eric Matthes"),
                Book("B002", "Clean Code", "Robert C. Martin"),
                Book("B003", "The Pragmatic Programmer", "Andrew Hunt and David Thomas"),
            )
            self.books.update({book.book_id: book for book in samples})
            changed = True
        if not self.members:
            samples = (
                Member("M001", "Alice Johnson", "alice123"),
                Member("M002", "Bob Smith", "bob456"),
            )
            self.members.update({member.member_id: member for member in samples})
            changed = True
        if changed:
            self._reconcile_active_loans()
            self._save_books()
            self._save_members()

    def login(self, uid: str, password: str) -> str | None:
        user_id = uid.strip().upper()
        if self.librarians.get(user_id) == password:
            return "librarian"
        if user_id in self.members and self.members[user_id].password == password:
            return "member"
        return None

    def add_book(self, book_id: str, title: str, author: str) -> tuple[bool, str]:
        bid = book_id.strip().upper()
        if not bid or not title.strip() or not author.strip():
            return False, "Please fill in all fields."
        if bid in self.books:
            return False, "Book ID already exists."
        self.books[bid] = Book(bid, title, author)
        self._save_books()
        return True, "Book added successfully."

    def add_member(self, member_id: str, name: str, password: str) -> tuple[bool, str]:
        mid = member_id.strip().upper()
        if not mid or not name.strip() or not password:
            return False, "Please fill in all fields."
        if mid in self.members or mid in self.librarians:
            return False, "User ID already exists."
        self.members[mid] = Member(mid, name, password)
        self._save_members()
        return True, "Member registered successfully."

    def search_books(self, query: str) -> list[Book]:
        q = query.strip().lower()
        return [
            book
            for book in self.books.values()
            if q in book.book_id.lower() or q in book.title.lower() or q in book.author.lower()
        ]

    def borrow_book(self, member_id: str, book_id: str) -> tuple[bool, str]:
        mid, bid = member_id.strip().upper(), book_id.strip().upper()
        if mid not in self.members:
            return False, "Member not found."
        if bid not in self.books:
            return False, "Book not found."
        if not self.books[bid].available:
            return False, "Book is already on loan."
        loan_id = f"L{self.next_loan:03d}"
        self.next_loan += 1
        loan = Loan(loan_id, mid, bid)
        self.loans[loan_id] = loan
        self.books[bid].available = False
        self.members[mid].loans.append(bid)
        self._save_all()
        return True, f"Book borrowed successfully. Due date: {loan.due_date}"

    def return_book(self, member_id: str, book_id: str) -> tuple[bool, str]:
        mid, bid = member_id.strip().upper(), book_id.strip().upper()
        found = next(
            (loan for loan in self.loans.values() if loan.member_id == mid and loan.book_id == bid),
            None,
        )
        if found is None:
            return False, "Active loan not found for that member and book."
        del self.loans[found.loan_id]
        if bid in self.books:
            self.books[bid].available = True
        if mid in self.members and bid in self.members[mid].loans:
            self.members[mid].loans.remove(bid)
        self._save_all()
        return True, "Book returned successfully."

    def all_loans(self) -> list[Loan]:
        return sorted(self.loans.values(), key=lambda loan: loan.due_date)

    def member_loans(self, member_id: str) -> list[Loan]:
        mid = member_id.strip().upper()
        return [loan for loan in self.all_loans() if loan.member_id == mid]

    def _save_all(self) -> None:
        self._save_loans()
        self._save_books()
        self._save_members()

    def _save_books(self) -> None:
        save_csv(BOOKS_FILE, ["book_id", "title", "author", "available"], [b.to_dict() for b in self.books.values()])

    def _save_members(self) -> None:
        save_csv(MEMBERS_FILE, ["member_id", "name", "password", "active_loans"], [m.to_dict() for m in self.members.values()])

    def _save_loans(self) -> None:
        save_csv(LOANS_FILE, ["loan_id", "member_id", "book_id", "borrow_date", "due_date"], [loan.to_dict() for loan in self.loans.values()])

    def _save_librarians(self) -> None:
        rows = [{"librarian_id": uid, "password": password} for uid, password in self.librarians.items()]
        save_csv(LIBRARIANS_FILE, ["librarian_id", "password"], rows)


class LibraryApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.lib = Library()
        self.user_id: str | None = None
        self.role: str | None = None
        self.root.title("Library Book Loan System")
        self.root.geometry("1040x780")
        self.root.minsize(880, 720)
        self.root.configure(bg=LIGHT_BLUE)
        self._configure_style()
        self.show_login()

    def _configure_style(self) -> None:
        self.root.option_add("*Font", ("Arial", 11))
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=36, font=("Arial", 11), background=WHITE,
                        foreground=TEXT, fieldbackground=WHITE, borderwidth=0)
        style.configure("Treeview.Heading", background=LIGHT_BLUE, foreground=TEXT,
                        font=("Arial", 10, "bold"), padding=(12, 12), relief="flat")
        style.map("Treeview", background=[("selected", BLUE)], foreground=[("selected", WHITE)])
        style.map("Treeview.Heading", background=[("active", BORDER)])
        style.configure("Accent.TButton", background=BLUE, foreground=WHITE,
                        font=("Arial", 11, "bold"), padding=(20, 10), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#115E59"), ("pressed", DARK_BLUE)])

    def _clear(self) -> None:
        self.root.unbind("<Return>")
        for widget in self.root.winfo_children():
            widget.destroy()

    def _header(self, title: str, subtitle: str = "") -> None:
        bar = tk.Frame(self.root, bg=DARK_BLUE, padx=32, pady=20)
        bar.pack(fill="x")
        tk.Label(bar, text="LIBRARY  /  BOOK LOAN SYSTEM", bg=DARK_BLUE, fg="#7DD3C7",
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(bar, text=title, bg=DARK_BLUE, fg=WHITE,
                 font=("Arial", 25, "bold")).pack(anchor="w", pady=(8, 3))
        if subtitle:
            tk.Label(bar, text=subtitle, bg=DARK_BLUE, fg="#CBD5E1",
                     font=("Arial", 11)).pack(anchor="w")

    def _card(self, width: int = 560) -> tk.Frame:
        shell = tk.Frame(self.root, bg=LIGHT_BLUE)
        shell.pack(fill="both", expand=True, padx=28, pady=(22, 8))
        card = tk.Frame(shell, bg=WHITE, highlightbackground=BORDER,
                        highlightthickness=1, padx=28, pady=22)
        card.pack(fill="both", expand=True)
        card.configure(width=width)
        return card

    def _btn(self, parent: tk.Widget, text: str, command, colour: str = BLUE, width: int = 24) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command, style="Accent.TButton",
                            width=width, cursor="hand2")
        button.pack(pady=(16, 6))
        return button

    def _entry(self, parent: tk.Widget, label: str, password: bool = False) -> tk.Entry:
        tk.Label(parent, text=label, bg=WHITE, fg=TEXT,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(14, 6))
        entry = tk.Entry(parent, width=42, show="*" if password else "", font=("Arial", 12),
                         bg="#F8FAFC", fg=TEXT, insertbackground=BLUE, relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE)
        entry.pack(fill="x", ipady=10)
        return entry

    def _dashboard(self, actions, member: bool = False) -> None:
        loans = self.lib.member_loans(self.user_id or "") if member else self.lib.all_loans()
        stats = tk.Frame(self.root, bg=LIGHT_BLUE)
        stats.pack(fill="x", padx=28, pady=(22, 0))
        overdue = sum(loan.due_date < date.today().isoformat() for loan in loans)
        values = (("Books in catalogue", len(self.lib.books)),
                  ("Available to borrow", sum(book.available for book in self.lib.books.values())),
                  ("My active loans" if member else "Active loans", len(loans)),
                  ("Overdue loans", overdue))
        for column, (label, value) in enumerate(values):
            stats.columnconfigure(column, weight=1, uniform="stat")
            tile = tk.Frame(stats, bg=WHITE, highlightbackground=BORDER,
                            highlightthickness=1, padx=16, pady=14)
            tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
            tk.Label(tile, text=str(value), bg=WHITE, fg=BLUE,
                     font=("Arial", 25, "bold")).pack(anchor="w")
            tk.Label(tile, text=label, bg=WHITE, fg=MUTED,
                     font=("Arial", 10)).pack(anchor="w", pady=(4, 0))
        card = self._card()
        tk.Label(card, text="What would you like to do?", bg=WHITE, fg=TEXT,
                 font=("Arial", 17, "bold")).pack(anchor="w")
        tk.Label(card, text="Choose an action to manage your library.", bg=WHITE,
                 fg=MUTED).pack(anchor="w", pady=(5, 16))
        grid = tk.Frame(card, bg=WHITE)
        grid.pack(fill="both", expand=True)
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="action")
        for index, (label, detail, command) in enumerate(actions):
            grid.rowconfigure(index // 2, weight=1)
            tile = tk.Frame(grid, bg="#F8FAFC", highlightbackground=BORDER,
                            highlightthickness=1, padx=14, pady=10)
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=5, pady=5)
            ttk.Button(tile, text=label, command=command, style="Accent.TButton",
                       cursor="hand2").pack(fill="x")
            tk.Label(tile, text=detail, bg="#F8FAFC", fg=MUTED,
                     font=("Arial", 10)).pack(anchor="w", pady=(8, 0))
        footer = tk.Frame(self.root, bg=LIGHT_BLUE)
        footer.pack(fill="x", padx=32, pady=(4, 16))
        tk.Label(footer, text="Standard loan period: 14 days", bg=LIGHT_BLUE,
                 fg=MUTED, font=("Arial", 10)).pack(side="left")
        ttk.Button(footer, text="Sign out", command=self._logout).pack(side="right")

    def _back(self) -> None:
        target = self.show_lib_menu if self.role == "librarian" else self.show_member_menu
        tk.Button(self.root, text="← Back to dashboard", command=target, bg=LIGHT_BLUE, fg=DARK_BLUE, relief="flat", font=("Arial", 10, "bold"), cursor="hand2").pack(pady=8)

    def _logout(self) -> None:
        self.user_id = None
        self.role = None
        self.show_login()

    def show_login(self) -> None:
        self._clear()
        self._header("Library Book Loan System", "Secure librarian and member access")
        card = self._card(480)
        card.pack_configure(fill="y", expand=False)
        tk.Label(card, text="Welcome back", bg=WHITE, fg=TEXT, font=("Arial", 19, "bold")).pack(pady=(0, 8))
        id_box = self._entry(card, "User ID")
        password_box = self._entry(card, "Password", password=True)

        def try_login() -> None:
            role = self.lib.login(id_box.get(), password_box.get())
            if role:
                self.user_id = id_box.get().strip().upper()
                self.role = role
                self.show_lib_menu() if role == "librarian" else self.show_member_menu()
            else:
                messagebox.showerror("Login failed", "Wrong ID or password.")

        self._btn(card, "Sign in to library", try_login)
        tk.Label(card, text="Sample librarian: LIB01 / admin\nSample members: M001 / alice123  •  M002 / bob456", bg=WHITE, fg=MUTED, font=("Arial", 9), justify="center").pack(pady=(12, 0))
        id_box.focus_set()
        self.root.bind("<Return>", lambda _event: try_login())

    def show_lib_menu(self) -> None:
        self._clear()
        self._header("Librarian dashboard", f"Welcome back, {self.user_id}. Here is your library at a glance.")
        self._dashboard((
            ("Add book", "Add a new title to the catalogue", self.pg_add_book),
            ("Register member", "Create a library member account", self.pg_add_member),
            ("Borrow book", "Issue a book to a member", self.pg_borrow),
            ("Return book", "Check a book back into the library", self.pg_return),
            ("Browse catalogue", "Find books by title, author or ID", self.pg_search),
            ("Active loans", "Review borrowing and due dates", self.pg_all_loans),
        ))

    def show_member_menu(self) -> None:
        self._clear()
        name = self.lib.members[self.user_id].name if self.user_id in self.lib.members else self.user_id
        self._header(f"Welcome, {name}", f"Member {self.user_id}  /  Your next read starts here.")
        self._dashboard((
            ("Browse catalogue", "Discover your next book", self.pg_search),
            ("Borrow book", "Borrow a title for 14 days", self.pg_borrow),
            ("Return book", "Return a book you have finished", self.pg_return),
            ("My loans", "See your books and due dates", self.pg_my_loans),
        ), member=True)

    def pg_add_book(self) -> None:
        self._clear(); self._header("Add New Book")
        card = self._card()
        id_box, title_box, author_box = self._entry(card, "Book ID"), self._entry(card, "Title"), self._entry(card, "Author")
        def submit() -> None:
            ok, msg = self.lib.add_book(id_box.get(), title_box.get(), author_box.get())
            (messagebox.showinfo if ok else messagebox.showerror)("Success" if ok else "Error", msg)
            if ok:
                for box in (id_box, title_box, author_box): box.delete(0, tk.END)
        self._btn(card, "Add Book", submit); self._back()

    def pg_add_member(self) -> None:
        self._clear(); self._header("Register New Member")
        card = self._card()
        id_box, name_box, password_box = self._entry(card, "Member ID"), self._entry(card, "Full name"), self._entry(card, "Password", True)
        def submit() -> None:
            ok, msg = self.lib.add_member(id_box.get(), name_box.get(), password_box.get())
            (messagebox.showinfo if ok else messagebox.showerror)("Success" if ok else "Error", msg)
            if ok:
                for box in (id_box, name_box, password_box): box.delete(0, tk.END)
        self._btn(card, "Add Member", submit, GREEN); self._back()

    def pg_borrow(self) -> None:
        self._clear(); self._header("Borrow Book", "Loans are due 14 days after borrowing")
        card = self._card()
        member_box = self._entry(card, "Member ID")
        if self.role == "member":
            member_box.insert(0, self.user_id or ""); member_box.configure(state="disabled")
        book_box = self._entry(card, "Book ID")
        def submit() -> None:
            ok, msg = self.lib.borrow_book(member_box.get(), book_box.get())
            (messagebox.showinfo if ok else messagebox.showerror)("Success" if ok else "Error", msg)
            if ok: book_box.delete(0, tk.END)
        self._btn(card, "Borrow Book", submit); self._back()

    def pg_return(self) -> None:
        self._clear(); self._header("Return Book")
        card = self._card()
        member_box = self._entry(card, "Member ID")
        if self.role == "member":
            member_box.insert(0, self.user_id or ""); member_box.configure(state="disabled")
        book_box = self._entry(card, "Book ID")
        def submit() -> None:
            ok, msg = self.lib.return_book(member_box.get(), book_box.get())
            (messagebox.showinfo if ok else messagebox.showerror)("Success" if ok else "Error", msg)
            if ok: book_box.delete(0, tk.END)
        self._btn(card, "Return Book", submit, GREEN); self._back()

    def _table_frame(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=WHITE)
        frame.pack(fill="both", expand=True)
        return frame

    def _scroll_table(self, frame: tk.Frame, tree: ttk.Treeview) -> None:
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.tag_configure("alternate", background="#F1F5F9")
        tree.tag_configure("overdue", background="#FFF1F2", foreground="#9F1239")

    def _book_table(self, parent: tk.Widget) -> ttk.Treeview:
        frame = self._table_frame(parent)
        tree = ttk.Treeview(frame, columns=("id", "title", "author", "status"), show="headings", height=10)
        headings = (("id", "Book ID", 90), ("title", "Title", 250), ("author", "Author", 220), ("status", "Status", 100))
        for key, text, width in headings:
            tree.heading(key, text=text); tree.column(key, width=width, anchor="w")
        self._scroll_table(frame, tree)
        return tree

    def pg_search(self) -> None:
        self._clear(); self._header("Search Books", "Search by ID, title, or author")
        card = self._card(820)
        search_row = tk.Frame(card, bg=WHITE); search_row.pack(fill="x", pady=(0, 14))
        query_box = tk.Entry(search_row, font=("Arial", 12), bg="#F8FAFC", fg=TEXT, insertbackground=BLUE, relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE); query_box.pack(side="left", fill="x", expand=True, ipady=6)
        table = self._book_table(card)
        def show_results() -> None:
            table.delete(*table.get_children())
            for index, book in enumerate(self.lib.search_books(query_box.get())):
                table.insert("", "end", values=(book.book_id, book.title, book.author, "Available" if book.available else "On loan"), tags=("alternate",) if index % 2 else ())
        ttk.Button(search_row, text="Search", command=show_results, style="Accent.TButton").pack(side="left", padx=(10, 0))
        query_box.bind("<Return>", lambda _event: show_results()); show_results(); self._back()

    def _loans_page(self, title: str, loans: list[Loan]) -> None:
        self._clear(); self._header(title)
        card = self._card(840)
        frame = self._table_frame(card)
        tree = ttk.Treeview(frame, columns=("loan", "member", "book", "title", "borrowed", "due"), show="headings", height=10)
        specs = (("loan", "Loan ID", 75), ("member", "Member", 85), ("book", "Book", 70), ("title", "Book title", 210), ("borrowed", "Borrowed", 100), ("due", "Due date", 100))
        for key, text, width in specs:
            tree.heading(key, text=text); tree.column(key, width=width, anchor="w")
        self._scroll_table(frame, tree)
        for index, loan in enumerate(loans):
            book_title = self.lib.books.get(loan.book_id).title if loan.book_id in self.lib.books else "Unknown book"
            tree.insert("", "end", values=(loan.loan_id, loan.member_id, loan.book_id, book_title, loan.borrow_date, loan.due_date),
                        tags=("overdue",) if loan.due_date < date.today().isoformat() else (("alternate",) if index % 2 else ()))
        if not loans:
            tk.Label(card, text="No active loans.", bg=WHITE, fg=MUTED, font=("Arial", 11)).pack(pady=12)
        self._back()

    def pg_all_loans(self) -> None:
        self._loans_page("All Active Loans and Due Dates", self.lib.all_loans())

    def pg_my_loans(self) -> None:
        self._loans_page("My Active Loans", self.lib.member_loans(self.user_id or ""))


def main() -> None:
    root = tk.Tk()
    LibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
