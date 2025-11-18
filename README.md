# Barcode label maker for IDPRT SP410

A simple Tkinter interface for creating 1" x 2" barcode labels with a centered Data Matrix code. The app sends PNG labels to the system print command so you can print to an IDPRT SP410 or similar thermal printer.

## Requirements
- Python 3.9 or newer
- A command-line print utility: `lp` (CUPS/macOS/Linux) or `lpr`/`print` (Windows Print Services)
- Printer configured in your OS (default name `IDPRT_SP410`, override with `BARCODE_PRINTER`)
- Dependencies from `requirements.txt`

Install the Python dependencies before running the app:

```bash
pip install -r requirements.txt
```

### Windows printing notes
- Install the SP410 driver and set the printer as the default or use `BARCODE_PRINTER` to target it explicitly.
- For USB-connected printers, the app prefers the built-in `print` command and targets the port named by `WINDOWS_PRINT_PORT`. It defaults to `Port_#0001.Hub_#0002` per your setup. If your port differs, set it before running:

  ```powershell
  set WINDOWS_PRINT_PORT=USB001
  python barcode_app.py
  ```

- If you see `WinError 2` or "system cannot find the file specified," enable **Print and Document Services → LPR Port Monitor** in Windows Optional Features so `lpr` is available on your PATH.
- The Windows `lpr` command requires a server (`-S`) and queue (`-P`). The app will prompt for these if they are not set and will cache what you enter for the session. You can also set them up front via `LPR_SERVER` and `LPR_QUEUE` (or `BARCODE_PRINTER` for the queue name), e.g.:

  ```powershell
  set LPR_SERVER=192.168.1.50
  set LPR_QUEUE=IDPRT_SP410
  python barcode_app.py
  ```

- Media defaults to `Custom.2x1in`; adjust the driver media or set `BARCODE_MEDIA` if the name differs.

## Running
Execute the GUI with:

```bash
python barcode_app.py
```

The app will prompt for booth, optional inventory number, description, and price (in cents, e.g., `400` for $4.00). After choosing the quantity, it renders and submits the labels to the configured printer.
