"""Tkinter user interface (four tabs: Bookings, Rooms, Reports, Compare)."""
import functools
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from . import analysis, reports
from .models import ROOM_TYPES, SOURCES, STATUSES, ValidationError, parse_date
from .storage import StorageError


def guarded(method):
    """Show friendly error dialogs instead of crashing the window."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (ValidationError, StorageError) as exc:
            messagebox.showerror("Cannot complete action", str(exc))
        except Exception as exc:  # last line of defence for unexpected bugs
            messagebox.showerror("Unexpected error", f"{type(exc).__name__}: {exc}")
    return wrapper


def _field(parent, label, col, values=None, width=12, default=""):
    """Label + entry (or read-only combobox) in row 0 of parent. Returns (variable, widget)."""
    ttk.Label(parent, text=label).grid(row=0, column=col * 2, padx=(6, 2), pady=4, sticky="e")
    var = tk.StringVar(value=default)
    if values is not None:
        widget = ttk.Combobox(parent, textvariable=var, values=list(values), width=width, state="readonly")
    else:
        widget = ttk.Entry(parent, textvariable=var, width=width)
    widget.grid(row=0, column=col * 2 + 1, padx=(0, 6), pady=4)
    return var, widget


def _make_tree(parent, columns, widths):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=6, pady=4)
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)
    for name, width in zip(columns, widths):
        tree.heading(name, text=name)
        tree.column(name, width=width, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


class HotelApp(tk.Tk):
    def __init__(self, manager):
        super().__init__()
        self.title("Hotel Booking Manager")
        self.geometry("1150x760")
        self.manager = manager
        self.current_fig = None
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, anchor="w", relief="sunken").pack(side="bottom", fill="x")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)
        tabs = {}
        for name in ("Bookings", "Rooms", "Reports", "Compare"):
            tabs[name] = ttk.Frame(notebook)
            notebook.add(tabs[name], text=name)
        self._build_bookings(tabs["Bookings"])
        self._build_rooms(tabs["Rooms"])
        self._build_reports(tabs["Reports"])
        self._build_compare(tabs["Compare"])
        self._set_default_periods()
        self.refresh_rooms()
        self.refresh_bookings()

    # ------------------------------------------------------------ helpers
    def _frames(self):
        return analysis.to_frames(self.manager.rooms, self.manager.bookings)

    def _show_figure(self, container, fig):
        for child in container.winfo_children():
            child.destroy()
        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.current_fig = fig

    def _set_default_periods(self):
        span = analysis.data_range(self._frames()[1])
        year = span[0].year if span else date.today().year
        last = span[1].year if span else year
        for var, value in ((self.rp_start, date(year, 1, 1)), (self.rp_end, date(year, 12, 31)),
                           (self.a_start, date(last - 1, 6, 1)), (self.a_end, date(last - 1, 8, 31)),
                           (self.b_start, date(last, 6, 1)), (self.b_end, date(last, 8, 31))):
            var.set(str(value))

    # ------------------------------------------------------- bookings tab
    def _build_bookings(self, tab):
        f = ttk.LabelFrame(tab, text="Search / filter (date range matches stays that overlap it)")
        f.pack(fill="x", padx=6, pady=4)
        self.f_guest, _ = _field(f, "Guest", 0, width=14)
        self.f_type, _ = _field(f, "Room type", 1, [""] + list(ROOM_TYPES), 9)
        self.f_status, _ = _field(f, "Status", 2, [""] + list(STATUSES), 11)
        self.f_source, _ = _field(f, "Source", 3, [""] + list(SOURCES), 13)
        self.f_from, _ = _field(f, "From", 4, width=11)
        self.f_to, _ = _field(f, "To", 5, width=11)
        ttk.Button(f, text="Search", command=self.refresh_bookings).grid(row=0, column=12, padx=4)
        ttk.Button(f, text="Clear", command=self.clear_filters).grid(row=0, column=13, padx=4)

        self.tree = _make_tree(tab, ("ID", "Guest", "Room", "Type", "Check-in", "Check-out", "Nights", "Source", "Status"),
                               (70, 170, 60, 80, 95, 95, 60, 110, 100))

        a = ttk.LabelFrame(tab, text="New booking (dates as YYYY-MM-DD)")
        a.pack(fill="x", padx=6, pady=4)
        self.n_guest, _ = _field(a, "Guest", 0, width=16)
        self.n_room, self.room_combo = _field(a, "Room", 1, values=[], width=8)
        self.n_in, _ = _field(a, "Check-in", 2, width=11)
        self.n_out, _ = _field(a, "Check-out", 3, width=11)
        self.n_source, _ = _field(a, "Source", 4, SOURCES, 13, SOURCES[0])
        ttk.Button(a, text="Add booking", command=self.add_booking).grid(row=0, column=10, padx=6)

        s = ttk.LabelFrame(tab, text="Update status of the selected booking")
        s.pack(fill="x", padx=6, pady=4)
        self.new_status, _ = _field(s, "New status", 0, STATUSES, 12, STATUSES[1])
        ttk.Button(s, text="Apply", command=self.update_status).grid(row=0, column=2, padx=6)

    @guarded
    def refresh_bookings(self):
        results = self.manager.search(
            guest=self.f_guest.get().strip(), room_type=self.f_type.get(), status=self.f_status.get(),
            source=self.f_source.get(), start=self.f_from.get().strip() or None,
            end=self.f_to.get().strip() or None)
        self.tree.delete(*self.tree.get_children())
        for b in results:
            room = self.manager.get_room(b.room_no)
            self.tree.insert("", "end", iid=b.booking_id, values=(
                b.booking_id, b.guest, b.room_no, room.room_type if room else "?",
                b.check_in, b.check_out, b.nights, b.source, b.status))
        self.status_var.set(f"{len(results)} booking(s) shown")

    def clear_filters(self):
        for var in (self.f_guest, self.f_type, self.f_status, self.f_source, self.f_from, self.f_to):
            var.set("")
        self.refresh_bookings()

    @guarded
    def add_booking(self):
        booking = self.manager.add_booking(self.n_guest.get(), self.n_room.get(),
                                           self.n_in.get(), self.n_out.get(), self.n_source.get())
        self.n_guest.set("")
        self.refresh_bookings()
        self.status_var.set(f"Added booking {booking.booking_id}")

    @guarded
    def update_status(self):
        selected = self.tree.selection()
        if not selected:
            raise ValidationError("Select a booking in the table first.")
        booking = self.manager.update_status(selected[0], self.new_status.get())
        self.refresh_bookings()
        self.status_var.set(f"{booking.booking_id} is now {booking.status}")

    # ---------------------------------------------------------- rooms tab
    def _build_rooms(self, tab):
        self.room_tree = _make_tree(tab, ("Room", "Type", "Nightly rate"), (120, 140, 140))
        a = ttk.LabelFrame(tab, text="Add room")
        a.pack(fill="x", padx=6, pady=4)
        self.r_no, _ = _field(a, "Room no.", 0, width=8)
        self.r_type, _ = _field(a, "Type", 1, ROOM_TYPES, 10, ROOM_TYPES[0])
        self.r_rate, _ = _field(a, "Nightly rate", 2, width=10)
        ttk.Button(a, text="Add room", command=self.add_room).grid(row=0, column=6, padx=6)

    @guarded
    def add_room(self):
        self.manager.add_room(self.r_no.get(), self.r_type.get(), self.r_rate.get())
        self.r_no.set("")
        self.r_rate.set("")
        self.refresh_rooms()

    def refresh_rooms(self):
        self.room_tree.delete(*self.room_tree.get_children())
        for room in self.manager.rooms:
            self.room_tree.insert("", "end", values=(room.room_no, room.room_type, f"{room.rate:.2f}"))
        self.room_combo["values"] = [r.room_no for r in self.manager.rooms]

    # -------------------------------------------------------- reports tab
    def _build_reports(self, tab):
        c = ttk.LabelFrame(tab, text="Reporting period (YYYY-MM-DD)")
        c.pack(fill="x", padx=6, pady=4)
        self.rp_start, _ = _field(c, "Start", 0, width=11)
        self.rp_end, _ = _field(c, "End", 1, width=11)
        buttons = (("Summary", self.show_summary), ("Monthly occupancy", self.chart_monthly),
                   ("Booking sources", self.chart_sources), ("Room usage", self.chart_rooms),
                   ("Save chart...", self.save_chart))
        for i, (text, command) in enumerate(buttons):
            ttk.Button(c, text=text, command=command).grid(row=0, column=4 + i, padx=4)
        body = ttk.PanedWindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=4)
        left = ttk.Frame(body)
        self.summary_tree = _make_tree(left, ("Measure", "Value"), (170, 90))
        note = "Assumptions:\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(analysis.ASSUMPTIONS, 1))
        ttk.Label(left, text=note, wraplength=290, justify="left", font=("TkDefaultFont", 8)).pack(padx=6, pady=4)
        self.chart_frame = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(self.chart_frame, weight=3)

    def _period(self):
        return parse_date(self.rp_start.get()), parse_date(self.rp_end.get())

    @guarded
    def show_summary(self):
        start, end = self._period()
        rooms, bookings = self._frames()
        self.summary_tree.delete(*self.summary_tree.get_children())
        for key, value in analysis.period_metrics(bookings, rooms, start, end).items():
            self.summary_tree.insert("", "end", values=(key, value))
        self.status_var.set(f"Summary for {start} to {end}")

    @guarded
    def chart_monthly(self):
        start, _ = self._period()
        rooms, bookings = self._frames()
        fig = reports.fig_monthly_occupancy(analysis.monthly_summary(bookings, rooms, start.year), start.year)
        self._show_figure(self.chart_frame, fig)

    @guarded
    def chart_sources(self):
        start, end = self._period()
        _, bookings = self._frames()
        fig = reports.fig_source_share(analysis.by_source(bookings, start, end), f"({start} to {end})")
        self._show_figure(self.chart_frame, fig)

    @guarded
    def chart_rooms(self):
        start, end = self._period()
        rooms, bookings = self._frames()
        fig = reports.fig_room_usage(analysis.room_usage(bookings, rooms, start, end), f"({start} to {end})")
        self._show_figure(self.chart_frame, fig)

    @guarded
    def save_chart(self):
        if self.current_fig is None:
            raise ValidationError("Show a chart first, then save it.")
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG image", "*.png"), ("PDF", "*.pdf")])
        if path:
            reports.save_figure(self.current_fig, path)
            self.status_var.set(f"Chart saved to {path}")

    # -------------------------------------------------------- compare tab
    def _build_compare(self, tab):
        c = ttk.LabelFrame(tab, text="Compare two periods (YYYY-MM-DD)")
        c.pack(fill="x", padx=6, pady=4)
        self.a_start, _ = _field(c, "A start", 0, width=11)
        self.a_end, _ = _field(c, "A end", 1, width=11)
        self.b_start, _ = _field(c, "B start", 2, width=11)
        self.b_end, _ = _field(c, "B end", 3, width=11)
        self.c_type, _ = _field(c, "Room type", 4, [""] + list(ROOM_TYPES), 9)
        ttk.Button(c, text="Compare", command=self.compare).grid(row=0, column=10, padx=6)
        ttk.Button(c, text="Save chart...", command=self.save_chart).grid(row=0, column=11, padx=4)
        self.cmp_tree = _make_tree(tab, ("Measure", "Period A", "Period B", "Change (%)"), (220, 120, 120, 110))
        self.cmp_chart = ttk.Frame(tab)
        self.cmp_chart.pack(fill="both", expand=True, padx=6, pady=4)

    @guarded
    def compare(self):
        a_s, a_e = parse_date(self.a_start.get()), parse_date(self.a_end.get())
        b_s, b_e = parse_date(self.b_start.get()), parse_date(self.b_end.get())
        rooms, bookings = self._frames()
        table = analysis.compare_periods(bookings, rooms, a_s, a_e, b_s, b_e, self.c_type.get() or None)
        self.cmp_tree.delete(*self.cmp_tree.get_children())
        for row in table.itertuples(index=False):
            change = "n/a" if row[3] != row[3] else row[3]  # NaN check
            self.cmp_tree.insert("", "end", values=(row[0], row[1], row[2], change))
        by_type = analysis.room_type_comparison(bookings, rooms, a_s, a_e, b_s, b_e)
        fig = reports.fig_room_type_comparison(by_type, f"A: {a_s} to {a_e}", f"B: {b_s} to {b_e}")
        self._show_figure(self.cmp_chart, fig)
