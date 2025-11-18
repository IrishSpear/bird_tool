# Barcode label maker for IDPRT SP410

A simple Tkinter interface for creating 1" x 2" barcode labels with a centered Data Matrix code. The app sends PNG labels to CUPS via `lp` so you can print to an IDPRT SP410 or similar thermal printer.

## Requirements
- Python 3.9 or newer
- CUPS/`lp` available on the system
- Printer configured in CUPS (default name `IDPRT_SP410`, override with `BARCODE_PRINTER`)
- Dependencies from `requirements.txt`

Install the Python dependencies before running the app:

```bash
pip install -r requirements.txt
```

## Running
Execute the GUI with:

```bash
python barcode_app.py
```

The app will prompt for booth, optional inventory number, description, and price (in cents, e.g., `400` for $4.00). After choosing the quantity, it renders and submits the labels to the configured printer. Media defaults to `Custom.2x1in`; override with `BARCODE_MEDIA` if your CUPS media name differs.
