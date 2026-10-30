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

BLUE = "#1565C0"
DARK_BLUE = "#0D47A1"
LIGHT_BLUE = "#E3F2FD"
WHITE = "#FFFFFF"
GREEN = "#2E7D32"
TEXT = "#16324F"


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
        self.root.geometry("920x650")
        self.root.minsize(760, 560)
        self.root.configure(bg=LIGHT_BLUE)
        self._configure_style()
        self.show_login()

    def _configure_style(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Arial", 10), background=WHITE, fieldbackground=WHITE)
        style.configure("Treeview.Heading", background=BLUE, foreground=WHITE, font=("Arial", 10, "bold"))

    def _clear(self) -> None:
        self.root.unbind("<Return>")
        for widget in self.root.winfo_children():
            widget.destroy()

    def _header(self, title: str, subtitle: str = "") -> None:
        bar = tk.Frame(self.root, bg=DARK_BLUE, height=90)
        bar.pack(fill="x")
        tk.Label(bar, text=title, bg=DARK_BLUE, fg=WHITE, font=("Arial", 24, "bold")).pack(pady=(16, 2))
        if subtitle:
            tk.Label(bar, text=subtitle, bg=DARK_BLUE, fg=WHITE, font=("Arial", 10)).pack()

    def _card(self, width: int = 560) -> tk.Frame:
        card = tk.Frame(self.root, bg=WHITE, highlightbackground="#BBDEFB", highlightthickness=1, padx=28, pady=22)
        card.pack(pady=25, padx=25, fill="both", expand=False)
        card.configure(width=width)
        return card

    def _btn(self, parent: tk.Widget, text: str, command, colour: str = BLUE, width: int = 24) -> tk.Button:
        button = tk.Button(parent, text=text, command=command, bg=colour, fg=WHITE, activebackground=DARK_BLUE, activeforeground=WHITE, relief="flat", font=("Arial", 11, "bold"), width=width, pady=9, cursor="hand2")
        button.pack(pady=7)
        return button

    def _entry(self, parent: tk.Widget, label: str, password: bool = False) -> tk.Entry:
        tk.Label(parent, text=label, bg=WHITE, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor="w", pady=(8, 3))
        entry = tk.Entry(parent, width=42, show="*" if password else "", font=("Arial", 11), relief="solid", bd=1)
        entry.pack(fill="x", ipady=6)
        return entry

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
        tk.Label(card, text="Sign in", bg=WHITE, fg=TEXT, font=("Arial", 19, "bold")).pack(pady=(0, 8))
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

        self._btn(card, "Login", try_login)
        tk.Label(card, text="Sample librarian: LIB01 / admin\nSample members: M001 / alice123  •  M002 / bob456", bg=WHITE, fg="#546E7A", font=("Arial", 9), justify="center").pack(pady=(12, 0))
        id_box.focus_set()
        self.root.bind("<Return>", lambda _event: try_login())

    def show_lib_menu(self) -> None:
        self._clear()
        self._header("Librarian Dashboard", f"Signed in as {self.user_id}")
        card = self._card()
        for text, command, colour in (
            ("Add Book", self.pg_add_book, BLUE),
            ("Add Member", self.pg_add_member, GREEN),
            ("Borrow Book", self.pg_borrow, BLUE),
            ("Return Book", self.pg_return, GREEN),
            ("Search Books", self.pg_search, BLUE),
            ("Active Loans / Due Dates", self.pg_all_loans, GREEN),
            ("Logout", self._logout, DARK_BLUE),
        ):
            self._btn(card, text, command, colour, 30)

    def show_member_menu(self) -> None:
        self._clear()
        name = self.lib.members[self.user_id].name if self.user_id in self.lib.members else self.user_id
        self._header(f"Welcome, {name}", f"Member ID: {self.user_id}")
        card = self._card()
        for text, command, colour in (
            ("Borrow Book", self.pg_borrow, BLUE),
            ("Return Book", self.pg_return, GREEN),
            ("Search Books", self.pg_search, BLUE),
            ("My Loans", self.pg_my_loans, GREEN),
            ("Logout", self._logout, DARK_BLUE),
        ):
            self._btn(card, text, command, colour, 30)

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

    def _book_table(self, parent: tk.Widget) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=("id", "title", "author", "status"), show="headings", height=13)
        headings = (("id", "Book ID", 90), ("title", "Title", 250), ("author", "Author", 220), ("status", "Status", 100))
        for key, text, width in headings:
            tree.heading(key, text=text); tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def pg_search(self) -> None:
        self._clear(); self._header("Search Books", "Search by ID, title, or author")
        card = self._card(820)
        search_row = tk.Frame(card, bg=WHITE); search_row.pack(fill="x", pady=(0, 14))
        query_box = tk.Entry(search_row, font=("Arial", 11)); query_box.pack(side="left", fill="x", expand=True, ipady=6)
        table = self._book_table(card)
        def show_results() -> None:
            table.delete(*table.get_children())
            for book in self.lib.search_books(query_box.get()):
                table.insert("", "end", values=(book.book_id, book.title, book.author, "Available" if book.available else "On loan"))
        tk.Button(search_row, text="Search", command=show_results, bg=BLUE, fg=WHITE, relief="flat", padx=24, pady=7).pack(side="left", padx=(10, 0))
        query_box.bind("<Return>", lambda _event: show_results()); show_results(); self._back()

    def _loans_page(self, title: str, loans: list[Loan]) -> None:
        self._clear(); self._header(title)
        card = self._card(840)
        tree = ttk.Treeview(card, columns=("loan", "member", "book", "title", "borrowed", "due"), show="headings", height=15)
        specs = (("loan", "Loan ID", 75), ("member", "Member", 85), ("book", "Book", 70), ("title", "Book title", 210), ("borrowed", "Borrowed", 100), ("due", "Due date", 100))
        for key, text, width in specs:
            tree.heading(key, text=text); tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        for loan in loans:
            book_title = self.lib.books.get(loan.book_id).title if loan.book_id in self.lib.books else "Unknown book"
            tree.insert("", "end", values=(loan.loan_id, loan.member_id, loan.book_id, book_title, loan.borrow_date, loan.due_date))
        if not loans:
            tk.Label(card, text="No active loans.", bg=WHITE, fg="#546E7A", font=("Arial", 11)).pack(pady=12)
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
