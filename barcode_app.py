"""
Tkinter-based label creation tool for IDPRT SP410 printers.

The app collects booth, optional inventory number, description, and a price in cents
(e.g. "400" -> $4.00). It renders a 1" x 2" label with a centered Data Matrix code,
booth number on the top-left, description bottom-left, and price bottom-right.

Labels are printed via the system ``lp`` command so the printer must be installed in
CUPS. Set ``PRINTER_NAME`` below to target a specific printer or leave ``None`` to use
the default printer.
"""
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

import tkinter as tk
from tkinter import messagebox, simpledialog


def _ensure_dependency(module_name: str, install_hint: str) -> None:
    """Fail fast with a clear message when optional dependencies are missing."""

    if importlib.util.find_spec(module_name) is None:
        raise SystemExit(
            f"Missing dependency '{module_name}'. Install requirements with: {install_hint}"
        )


_ensure_dependency("PIL", "pip install -r requirements.txt")
_ensure_dependency("pylibdmtx", "pip install -r requirements.txt")

from PIL import Image, ImageDraw, ImageFont
from pylibdmtx.pylibdmtx import encode

# Printer settings.
PRINTER_NAME = os.environ.get("BARCODE_PRINTER", "IDPRT_SP410")
MEDIA_OPTION = os.environ.get("BARCODE_MEDIA", "Custom.2x1in")
DPI = 203  # Typical resolution for 203 dpi thermal printers.
LABEL_WIDTH_IN = 2
LABEL_HEIGHT_IN = 1


@dataclass
class LabelData:
    booth: str
    inventory: str
    description: str
    price_cents: int

    @property
    def formatted_price(self) -> str:
        return f"${self.price_cents / 100:.2f}"

    @property
    def datamatrix_payload(self) -> str:
        """Return the exact payload string for the Data Matrix barcode."""
        parts = [self.booth.strip(), self.inventory.strip(), self.description.strip(), str(self.price_cents)]
        # Preserve the space for optional inventory by keeping the empty string in the join.
        return " ".join(parts)


def parse_price(price_value: str) -> int:
    """Parse a user-entered price into cents.

    Accepts integer strings ("400" -> 400 cents) or decimal forms ("4.00" -> 400 cents).
    """
    cleaned = price_value.strip().lstrip("$")
    if not cleaned:
        raise ValueError("Price is required")

    if "." in cleaned:
        dollars = float(cleaned)
        cents = round(dollars * 100)
    else:
        cents = int(cleaned)
    if cents < 0:
        raise ValueError("Price cannot be negative")
    return cents


def make_datamatrix(payload: str) -> Image.Image:
    encoded = encode(payload.encode("utf-8"))
    matrix = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)
    matrix = matrix.convert("1")  # Convert to 1-bit for crisp edges.
    return matrix


def render_label(label: LabelData) -> Image.Image:
    width_px = int(LABEL_WIDTH_IN * DPI)
    height_px = int(LABEL_HEIGHT_IN * DPI)
    image = Image.new("1", (width_px, height_px), color=1)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    # Text placements.
    booth_text = f"Booth {label.booth}" if label.booth else "Booth"
    draw.text((8, 6), booth_text, font=font, fill=0)

    desc_y = height_px - font.getbbox(label.description or " ")[3] - 6
    draw.text((8, desc_y), label.description, font=font, fill=0)

    price_text = label.formatted_price
    price_size = font.getbbox(price_text)
    price_x = width_px - price_size[2] - 8
    price_y = height_px - price_size[3] - 6
    draw.text((price_x, price_y), price_text, font=font, fill=0)

    # Data Matrix centered.
    matrix = make_datamatrix(label.datamatrix_payload)
    max_matrix_width = int(width_px * 0.6)
    max_matrix_height = int(height_px * 0.7)
    scale = min(max_matrix_width / matrix.width, max_matrix_height / matrix.height, 1)
    if scale < 1:
        new_size = (max(1, int(matrix.width * scale)), max(1, int(matrix.height * scale)))
        matrix = matrix.resize(new_size, Image.NEAREST)

    matrix_x = (width_px - matrix.width) // 2
    matrix_y = (height_px - matrix.height) // 2
    image.paste(matrix, (matrix_x, matrix_y))

    return image


def _pick_print_command() -> tuple[list[str], str]:
    """Choose a platform-appropriate print command.

    Returns a tuple of (command_prefix, style) where ``style`` is one of
    ``"lp"``, ``"lpr-posix"``, or ``"lpr-windows"``. Raises a SystemError with
    guidance when no supported command exists.
    """

    system = platform.system()

    if shutil.which("lp"):
        return ["lp"], "lp"

    if shutil.which("lpr"):
        style = "lpr-windows" if system == "Windows" else "lpr-posix"
        return ["lpr"], style

    if system == "Windows":
        raise SystemError(
            "No command-line printer interface found. Enable the Windows 'Print and "
            "Document Services' optional feature for 'LPR Port Monitor', or install "
            "CUPS-compatible tools and ensure 'lp' or 'lpr' is on PATH."
        )

    raise SystemError(
        "No 'lp' or 'lpr' command found. Install CUPS or add a compatible print "
        "utility to your PATH."
    )


_cached_windows_target: tuple[str, str] | None = None


def _resolve_windows_lpr_target(root: tk.Tk | None = None) -> tuple[str, str]:
    """Return the (server, queue) tuple for Windows ``lpr``.

    Prefer environment variables, but if they are missing and a Tk root is
    available, prompt the user interactively. Values are cached for the current
    session to avoid repeated prompts.
    """

    global _cached_windows_target

    if _cached_windows_target:
        return _cached_windows_target

    server = os.environ.get("LPR_SERVER")
    queue = os.environ.get("LPR_QUEUE") or PRINTER_NAME

    if (not server or not queue) and root is not None:
        server = server or simpledialog.askstring(
            "LPR Server", "Enter the LPR server hostname or IP address:", parent=root
        )
        queue = queue or simpledialog.askstring(
            "LPR Queue", "Enter the LPR queue/share name:", parent=root
        )

    if server and queue:
        _cached_windows_target = (server.strip(), queue.strip())
        return _cached_windows_target

    raise SystemError(
        "Windows 'lpr' requires a server (-S) and queue (-P). Provide them via "
        "LPR_SERVER and LPR_QUEUE (or BARCODE_PRINTER), or supply values when "
        "prompted. Ensure the LPR Port Monitor feature is enabled."
    )


def send_to_printer(image: Image.Image, copies: int = 1, *, root: tk.Tk | None = None) -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name, "PNG")
        tmp_path = tmp.name

    command_prefix, style = _pick_print_command()

    try:
        if style == "lp":
            command = command_prefix + [
                "-n",
                str(copies),
                "-o",
                "fit-to-page",
                "-o",
                f"media={MEDIA_OPTION}",
            ]
            if PRINTER_NAME:
                command.extend(["-d", PRINTER_NAME])
            command.append(tmp_path)
            subprocess.run(command, check=True)

        elif style == "lpr-posix":
            command = command_prefix + ["-#", str(copies), "-o", "fit-to-page", "-o", f"media={MEDIA_OPTION}"]
            if PRINTER_NAME:
                command.extend(["-P", PRINTER_NAME])
            command.append(tmp_path)
            subprocess.run(command, check=True)

        elif style == "lpr-windows":
            server, queue = _resolve_windows_lpr_target(root=root)

            for _ in range(copies):
                command = command_prefix + ["-S", server, "-P", queue, "-o", "l", tmp_path]
                subprocess.run(command, check=True)

        else:  # pragma: no cover - defensive guard
            raise SystemError(f"Unsupported print style: {style}")
    except FileNotFoundError as exc:
        raise SystemError(
            "Could not invoke the system print command. Ensure 'lp' or 'lpr' is "
            "installed and available on PATH (Windows may require enabling the "
            "LPR Port Monitor optional feature)."
        ) from exc
    finally:
        os.remove(tmp_path)


def collect_label_data(root: tk.Tk) -> Optional[LabelData]:
    booth = simpledialog.askstring("Booth", "Enter booth number:", parent=root)
    if booth is None or not booth.strip():
        messagebox.showerror("Missing booth", "Booth number is required.")
        return None

    inventory = simpledialog.askstring("Inventory", "Enter inventory number (optional):", parent=root) or ""
    description = simpledialog.askstring("Description", "Enter product description:", parent=root)
    if description is None or not description.strip():
        messagebox.showerror("Missing description", "Description is required.")
        return None

    price_value = simpledialog.askstring("Price", "Enter price in cents (e.g. 400 for $4.00):", parent=root)
    if price_value is None:
        return None

    try:
        price_cents = parse_price(price_value)
    except ValueError as exc:
        messagebox.showerror("Invalid price", str(exc))
        return None

    return LabelData(booth=booth.strip(), inventory=inventory.strip(), description=description.strip(), price_cents=price_cents)


def prompt_copies(root: tk.Tk) -> Optional[int]:
    copies = simpledialog.askinteger("Copies", "How many labels should be printed?", minvalue=1, maxvalue=100, parent=root)
    return copies


def print_label_flow(root: tk.Tk) -> None:
    while True:
        data = collect_label_data(root)
        if not data:
            return

        copies = prompt_copies(root)
        if not copies:
            return

        try:
            image = render_label(data)
            send_to_printer(image, copies=copies, root=root)
            messagebox.showinfo("Printed", f"Sent {copies} label(s) to the printer.")
        except Exception as exc:  # pragma: no cover - user feedback
            messagebox.showerror("Print failed", str(exc))

        again = messagebox.askyesno("Another?", "Print another label?")
        if not again:
            return


def main() -> None:
    root = tk.Tk()
    root.title("IDPRT Barcode Tagger")
    root.geometry("320x120")

    description = tk.Label(root, text="Create 1\" x 2\" Data Matrix labels for an IDPRT SP410.")
    description.pack(pady=8)

    print_button = tk.Button(root, text="Print a Tag", command=lambda: print_label_flow(root))
    print_button.pack(pady=4)

    quit_button = tk.Button(root, text="Quit", command=root.destroy)
    quit_button.pack(pady=4)

    root.mainloop()


if __name__ == "__main__":
    main()
