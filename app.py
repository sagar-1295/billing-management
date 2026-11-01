import io
import json
import os
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "invoice_data.json"


@st.cache_data
def load_invoice_data():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


catalog = load_invoice_data()
company = catalog["company"]
customers = catalog["customers"]
items = catalog["items"]
themes = catalog["themes"]

st.set_page_config(page_title="Invoice App", layout="wide")


def get_theme_by_name(theme_name: str):
    for theme in themes:
        if theme["name"] == theme_name:
            return theme
    return themes[0]


def format_currency(value: float) -> str:
    return f"₹{value:,.2f}"


def resolve_font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    if bold:
        candidates = [
            p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") if "DejaVuSans.ttf" in p else p
            for p in candidates
        ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def build_invoice_html(customer, selected_line_items, invoice_no, invoice_date, gst_enabled, tax_rate, theme, owner_details):
    subtotal = sum(item["amount"] for item in selected_line_items)
    gst_amount = subtotal * tax_rate / 100 if gst_enabled else 0.0
    total = subtotal + gst_amount

    row_html = []
    for item in selected_line_items:
        row_html.append(
            """
            <tr>
                <td>{name}</td>
                <td>{qty} {unit}</td>
                <td>{rate}</td>
                <td>{amount}</td>
            </tr>
            """.format(
                name=item["name"],
                qty=item["quantity"],
                unit=item["unit"],
                rate=format_currency(item["price"]),
                amount=format_currency(item["amount"]),
            )
        )
    rows = "".join(row_html)

    subtotal_row_html = f"""
        <div class="totals-row">
            <span>Subtotal</span>
            <span>{format_currency(subtotal)}</span>
        </div>
    """ if gst_enabled else ""
    gst_row_html = f"""
        <div class="totals-row">
            <span>GST</span>
            <span>{format_currency(gst_amount)}</span>
        </div>
    """ if gst_enabled else ""

    customer_phone_html = f"{customer['phone']}<br>" if customer["phone"] else ""
    customer_email_html = f"{customer['email']}<br>" if customer["email"] else ""
    customer_address_html = customer["address"] if customer["address"] else ""
    customer_meta_html = f"{customer_phone_html}{customer_email_html}{customer_address_html}" if (customer_phone_html or customer_email_html or customer_address_html) else ""

    return f"""
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            background: #e5e7eb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 16px;
            -webkit-text-size-adjust: 100%;
            text-size-adjust: 100%;
        }}
        .invoice-paper {{
            width: 820px;
            max-width: 100%;
            min-height: 560px;
            margin: 0 auto;
            padding: 12px 18px 12px;
            border-radius: 18px;
            border: 1px solid {theme['border_color']};
            background: {theme['paper_bg']};
            color: {theme['text_color']};
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
        }}
        .invoice-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            padding-bottom: 8px;
            margin-bottom: 10px;
            border-bottom: 1px solid {theme['border_color']};
        }}
        .company-name {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.02em;
            color: {theme['accent']};
            line-height: 1.2;
        }}
        .invoice-date {{
            font-size: 18px;
            font-weight: 700;
            color: {theme['text_color']};
            white-space: nowrap;
            margin-top: 2px;
        }}
        .invoice-card {{
            min-height: 90px;
            padding: 4px 0 8px;
        }}
        .invoice-card .label {{
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: {theme['text_color']};
            margin-bottom: 4px;
        }}
        .customer-name {{
            font-size: 60px;
            font-weight: 900;
            line-height: 1.02;
            color: {theme['text_color']};
            letter-spacing: -0.06em;
            margin: 0 0 6px;
        }}
        .detail-text {{
            font-size: 16px;
            line-height: 1.5;
            color: {theme['muted_color']};
        }}
        .invoice-table-wrap {{
            border: 1px solid {theme['border_color']};
            border-radius: 16px;
            overflow: hidden;
            background: rgba(255,255,255,0.03);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}
        colgroup col:nth-child(1) {{ width: 42%; }}
        colgroup col:nth-child(2) {{ width: 18%; }}
        colgroup col:nth-child(3) {{ width: 20%; }}
        colgroup col:nth-child(4) {{ width: 20%; }}
        th, td {{
            border-bottom: 1px solid {theme['border_color']};
            padding: 10px 10px 9px;
            text-align: left;
            font-size: 15px;
            line-height: 1.35;
        }}
        th {{
            background: {theme['highlight_bg']};
            font-weight: 800;
            color: {theme['text_color']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 14px;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .totals {{
            margin-top: 14px;
            display: flex;
            justify-content: flex-end;
        }}
        .totals-box {{
            width: 300px;
            border: 1px solid {theme['border_color']};
            border-radius: 12px;
            background: rgba(255,255,255,0.05);
            padding: 10px 14px;
        }}
        .totals-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 17px;
            padding: 5px 0;
            border-bottom: 1px solid {theme['border_color']};
        }}
        .totals-row:last-child {{
            border-bottom: none;
            font-weight: 900;
            font-size: 26px;
        }}
        @media (max-width: 700px) {{
            .invoice-paper {{
                padding: 18px 12px 12px;
            }}
            .invoice-top {{
                flex-direction: column;
            }}
            .invoice-card, .invoice-details {{
                min-height: auto;
            }}
            th, td {{
                font-size: 0.78rem;
                padding: 10px 8px;
            }}
            .totals-box {{
                width: 100%;
            }}
            .totals-row {{
                font-size: 1rem;
            }}
            .totals-row:last-child {{
                font-size: 1.2rem;
            }}
        }}
        @media print {{
            @page {{
                size: A5 landscape;
                margin: 8mm;
            }}
            body {{ background: white; }}
            .invoice-paper {{
                box-shadow: none;
                border: none;
                margin: 0;
                width: 210mm;
                min-height: 148mm;
                max-width: none;
                padding: 0;
            }}
        }}
    </style>

    <div class="invoice-paper">
        <div class="invoice-header">
            <div class="company-name">{(owner_details.get('name') or 'Sagar Agency').strip() or 'Sagar Agency'}</div>
            <div class="invoice-date">Date: {invoice_date}</div>
        </div>

        <div class="invoice-card">
            <div class="label">Bill To</div>
            <div class="customer-name">{customer['name'] or 'Customer Name'}</div>
            <div class="detail-text">
                {customer_meta_html}
            </div>
        </div>

        <div class="invoice-table-wrap">
            <table>
                <colgroup>
                    <col>
                    <col>
                    <col>
                    <col>
                </colgroup>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Rate</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>

        <div class="totals">
            <div class="totals-box">
                {subtotal_row_html}
                {gst_row_html}
                <div class="totals-row">
                    <span>Total</span>
                    <span>{format_currency(total)}</span>
                </div>
            </div>
        </div>
    </div>
    """


def invoice_summary_text(invoice_no, invoice_date, customer, line_items, gst_enabled, gst_rate):
    lines = [
        "Sagar Agency Invoice",
        f"Invoice No: {invoice_no or 'N/A'}",
        f"Date: {invoice_date}",
        f"Customer: {customer['name'] or 'Customer Name'}",
        f"Phone: {customer['phone'] or 'N/A'}",
    ]
    if line_items:
        lines.append("Items:")
        for item in line_items:
            lines.append(f"- {item['name']} {item['quantity']} {item['unit']} @ {format_currency(item['price'])} = {format_currency(item['amount'])}")
    lines.append(f"GST Enabled: {'Yes' if gst_enabled else 'No'}")
    if gst_enabled:
        lines.append(f"GST Rate: {gst_rate}%")
    return "\n".join(lines)


@st.cache_data
def generate_pdf_invoice(invoice_no, invoice_date, customer, line_items, gst_enabled, gst_rate, owner_details):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5
    c.setTitle(f"Invoice {invoice_no or 'N/A'}")

    company_name = owner_details.get("name", "").strip() or "Sagar Agency"
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20, height - 28, company_name)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 20, height - 28, f"Date: {invoice_date}")

    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(20, height - 42, width - 20, height - 42)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20, height - 72, "Bill To")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20, height - 100, (customer.get("name", "") or "Customer Name").strip()[:45])

    c.setFont("Helvetica-Bold", 9)
    y = height - 150
    c.drawString(20, y, "Item")
    c.drawString(130, y, "Qty")
    c.drawString(190, y, "Rate")
    c.drawString(250, y, "Amount")

    y -= 18
    subtotal = 0.0
    c.setFont("Helvetica", 9)
    for item in line_items:
        subtotal += item["amount"]
        c.drawString(20, y, item["name"][:22])
        c.drawString(130, y, f"{item['quantity']} {item['unit']}")
        c.drawString(190, y, format_currency(item["price"]))
        c.drawString(250, y, format_currency(item["amount"]))
        y -= 18

    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(width - 150, y - 18, width - 20, y - 18)
    total_box_y = y - 42
    c.setFont("Helvetica-Bold", 9)
    c.drawString(width - 120, total_box_y + 16, "Total")
    c.drawRightString(width - 24, total_box_y + 16, format_currency(subtotal + (subtotal * gst_rate / 100 if gst_enabled else 0)))
    c.save()
    return buffer.getvalue()


@st.cache_data
def generate_invoice_image(invoice_no, invoice_date, customer, line_items, gst_enabled, gst_rate, owner_details, theme):
    html = build_invoice_html(
        customer=customer,
        selected_line_items=line_items,
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        gst_enabled=gst_enabled,
        tax_rate=gst_rate,
        theme=theme,
        owner_details=owner_details,
    )

    try:
        from playwright.sync_api import sync_playwright

        with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
            tmp.write("<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0;background:#e5e7eb'>" + html + "</body></html>")
            path = tmp.name

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1365, "height": 900}, device_scale_factor=1)
            page.goto("file://" + path, wait_until="networkidle")
            page.locator("body").screenshot(path=path + ".png")
            browser.close()

        with open(path + ".png", "rb") as img_file:
            screenshot_bytes = img_file.read()
        os.remove(path)
        os.remove(path + ".png")
        return screenshot_bytes
    except Exception:
        width, height = 1365, 900
        image = Image.new("RGB", (width, height), color=theme.get("paper_bg", "#f3f4f6"))
        draw = ImageDraw.Draw(image)
        margin = 50

        outline = theme.get("border_color", "#d1d5db")
        text_color = theme.get("text_color", "#111827")
        accent = theme.get("accent", "#111827")
        soft_bg = theme.get("highlight_bg", "#e8eaec")
        header_bg = theme.get("highlight_bg", "#e7ebee")

        draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=18, outline=outline, width=2, fill=theme.get("paper_bg", "#f3f4f6"))

        company_name = owner_details.get("name", "").strip() or "Sagar Agency"
        draw.text((margin, 18), company_name, font=resolve_font(24, bold=True), fill=accent)
        draw.text((width - 290, 18), f"Date: {invoice_date}", font=resolve_font(24, bold=True), fill=text_color)
        draw.line((margin, 62, width - margin, 62), fill=outline, width=2)

        bill_y = 90
        draw.text((margin, bill_y), "BILL TO", font=resolve_font(18, bold=True), fill=text_color)
        customer_name = (customer.get("name", "") or "Customer Name").strip() or "Customer Name"
        draw.text((margin, bill_y + 26), customer_name, font=resolve_font(56, bold=True), fill=text_color)

        table_top = 220
        table_left = margin
        table_width = width - (margin * 2)
        col_positions = [table_left, table_left + 470, table_left + 700, table_left + 930]
        headers = ["ITEM", "QTY", "RATE", "AMOUNT"]
        draw.rounded_rectangle((table_left, table_top, table_left + table_width, table_top + 48), radius=0, fill=header_bg)
        for idx, header in enumerate(headers):
            draw.text((col_positions[idx] + 12, table_top + 12), header, font=resolve_font(18, bold=True), fill=text_color)

        y = table_top + 54
        subtotal = 0.0
        row_height = 58
        for item in line_items:
            subtotal += item["amount"]
            draw.line((table_left, y, table_left + table_width, y), fill=outline, width=2)
            draw.text((table_left + 12, y + 12), item["name"][:24], font=resolve_font(18), fill=text_color)
            draw.text((col_positions[1] + 12, y + 12), f"{item['quantity']} {item['unit']}", font=resolve_font(18), fill=text_color)
            draw.text((col_positions[2] + 10, y + 12), format_currency(item["price"]), font=resolve_font(18), fill=text_color)
            draw.text((col_positions[3] + 8, y + 12), format_currency(item["amount"]), font=resolve_font(18), fill=text_color)
            y += row_height

        total_box_x = width - 360
        total_box_y = y + 24
        draw.rounded_rectangle((total_box_x, total_box_y, total_box_x + 260, total_box_y + 92), radius=12, fill=soft_bg)

        if gst_enabled:
            gst_value = subtotal * gst_rate / 100
            total_value = subtotal + gst_value
            draw.text((total_box_x + 18, total_box_y + 16), "Subtotal", font=resolve_font(18), fill=text_color)
            draw.text((total_box_x + 165, total_box_y + 16), format_currency(subtotal), font=resolve_font(18), fill=text_color)
            draw.text((total_box_x + 18, total_box_y + 48), "GST", font=resolve_font(18), fill=text_color)
            draw.text((total_box_x + 165, total_box_y + 48), format_currency(gst_value), font=resolve_font(18), fill=text_color)
            draw.text((total_box_x + 18, total_box_y + 76), "Total", font=resolve_font(22, bold=True), fill=text_color)
            draw.text((total_box_x + 165, total_box_y + 76), format_currency(total_value), font=resolve_font(22, bold=True), fill=text_color)
        else:
            total_value = subtotal
            draw.text((total_box_x + 18, total_box_y + 28), "Total", font=resolve_font(22, bold=True), fill=text_color)
            draw.text((total_box_x + 165, total_box_y + 28), format_currency(total_value), font=resolve_font(22, bold=True), fill=text_color)

        with io.BytesIO() as buf:
            image.save(buf, format="PNG")
            return buf.getvalue()


@st.cache_data
def generate_invoice_jpeg(invoice_no, invoice_date, customer, line_items, gst_enabled, gst_rate, owner_details, theme):
    png = generate_invoice_image(invoice_no, invoice_date, customer, line_items, gst_enabled, gst_rate, owner_details, theme)
    image = Image.open(io.BytesIO(png)).convert("RGB")
    with io.BytesIO() as buf:
        image.save(buf, format="JPEG", quality=95)
        return buf.getvalue()


st.markdown(
    """
    <style>
    html, body {{
        font-size: 16px;
        -webkit-text-size-adjust: 100%;
        text-size-adjust: 100%;
    }}
    .stApp {{
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        font-size: 16px;
    }}
    .block-container {{
        max-width: 1200px !important;
        padding-top: 1rem !important;
    }}
    .stSidebar, .stSidebar * {{
        font-size: 1rem !important;
    }}
    .stTextInput input, .stSelectbox div, .stMultiSelect div, .stDateInput input, .stNumberInput input {{
        font-size: 1rem !important;
    }}
    .stButton button, .stDownloadButton button {{
        font-size: 1rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Invoice Setup")
    st.caption("Sagar Agency billing workspace")

    theme_name = st.selectbox("Theme", [theme["name"] for theme in themes], index=0)
    theme = get_theme_by_name(theme_name)

    owner_name = st.text_input("Owner / Provider Name", value="")
    owner_phone = st.text_input("Owner Phone", value="")
    owner_email = st.text_input("Owner Email", value="")
    owner_address = st.text_area("Owner Address", value="", height=100)

    customer_name_input = st.text_input("Customer Name (custom or quick select)", value="")
    customer_name_select = st.selectbox("Quick Select Customer Name", ["", *[customer["name"] for customer in customers]], index=0)
    customer_name = customer_name_input.strip() or customer_name_select.strip()
    st.caption("Only the customer name is used for invoice output; add phone/email/address manually if you want them on the bill.")
    customer_phone = st.text_input("Customer Phone", value="")
    customer_email = st.text_input("Customer Email", value="")
    customer_address = st.text_area("Customer Address", value="", height=100)

    invoice_no = st.text_input("Invoice Number", value="")
    invoice_date = st.date_input("Invoice Date", value=date.today())
    gst_enabled = st.toggle("GST Enabled", value=False, help="Turn GST on or off for this invoice")
    gst_rate = st.number_input("GST Rate (%)", min_value=0.0, max_value=28.0, value=18.0, step=1.0, disabled=not gst_enabled)

    st.subheader("Items")
    item_name_input = st.text_input("Add item name manually", value="")
    predefined_items = [item["name"] for item in items]
    selected_item_names = st.multiselect("Choose items", predefined_items, default=[])
    selected_line_items = []

    for item_name in selected_item_names:
        item = next(item for item in items if item["name"] == item_name)
        qty = st.number_input(f"Quantity for {item['name']}", min_value=0.0, value=0.0, step=0.5, key=f"qty_{item_name}")
        unit = st.selectbox(f"Unit for {item['name']}", item["units"], index=0, key=f"unit_{item_name}")
        price = st.number_input(f"Price for {item['name']}", min_value=0.0, value=item["price"], step=1.0, key=f"price_{item_name}")
        if qty > 0:
            selected_line_items.append({
                "name": item["name"],
                "quantity": qty,
                "unit": unit,
                "price": price,
                "amount": qty * price,
            })

    if item_name_input.strip():
        item_name = item_name_input.strip()
        qty = st.number_input(f"Quantity for {item_name}", min_value=0.0, value=0.0, step=0.5, key=f"qty_manual_{item_name}")
        unit = st.selectbox(f"Unit for {item_name}", ["Nos", "KG"], index=0, key=f"unit_manual_{item_name}")
        custom_price = st.number_input(f"Price for {item_name}", min_value=0.0, value=0.0, step=1.0, key=f"price_manual_{item_name}")
        if qty > 0 and custom_price > 0:
            selected_line_items.append({
                "name": item_name,
                "quantity": qty,
                "unit": unit,
                "price": custom_price,
                "amount": qty * custom_price,
            })

    st.caption("Optional note: the invoice paper is sized like an A5 sheet for easy print preview.")

st.title("Invoice App")

if not selected_line_items:
    st.warning("Please select at least one item to generate the invoice.")
    st.stop()

owner_details = {
    "name": owner_name.strip(),
    "phone": owner_phone.strip(),
    "email": owner_email.strip(),
    "address": owner_address.strip(),
}
customer = {
    "name": customer_name.strip(),
    "phone": customer_phone.strip(),
    "email": customer_email.strip(),
    "address": customer_address.strip(),
}

invoice_html = build_invoice_html(
    customer,
    selected_line_items,
    invoice_no.strip() or "N/A",
    invoice_date.strftime("%d-%b-%Y"),
    gst_enabled,
    gst_rate,
    theme,
    owner_details,
)

components.html(invoice_html, height=1100, scrolling=True)

share_text = invoice_summary_text(
    invoice_no.strip() or "N/A",
    invoice_date.strftime("%d-%b-%Y"),
    customer,
    selected_line_items,
    gst_enabled,
    gst_rate,
)
share_html = f"""
<div>
  <button id="shareBtn" style="padding: 0.6rem 1rem; border-radius: 10px; background: #2563eb; color: white; border: none; font-weight: 700; cursor: pointer;">Share Invoice</button>
</div>
<script>
  const btn = document.getElementById('shareBtn');
  btn.addEventListener('click', async () => {{
    const text = {json.dumps(share_text)};
    if (navigator.share) {{
      try {{
        await navigator.share({{ title: 'Invoice', text: text, url: window.location.href }});
      }} catch (error) {{
        if (error && error.name !== 'AbortError') {{
          navigator.clipboard.writeText(text).then(() => alert('Invoice summary copied to clipboard.'));
        }}
      }}
    }} else if (navigator.clipboard) {{
      navigator.clipboard.writeText(text).then(() => alert('Invoice summary copied to clipboard.'));
    }} else {{
      alert('Sharing is not supported in this browser.');
    }}
  }});
</script>
"""
components.html(share_html, height=80)

st.subheader("Print / Share / Download")
col_print, col_pdf, col_png, col_jpeg = st.columns(4)

with col_print:
    if st.button("Print Invoice"):
        components.html("<script>window.print();</script>", height=0)

with col_pdf:
    st.download_button(
        label="Download PDF",
        data=generate_pdf_invoice(invoice_no.strip() or "N/A", invoice_date.strftime("%d-%b-%Y"), customer, selected_line_items, gst_enabled, gst_rate, owner_details),
        file_name=f"{(invoice_no.strip() or 'invoice')}.pdf",
        mime="application/pdf",
    )

with col_png:
    st.download_button(
        label="Download PNG",
        data=generate_invoice_image(invoice_no.strip() or "N/A", invoice_date.strftime("%d-%b-%Y"), customer, selected_line_items, gst_enabled, gst_rate, owner_details, theme),
        file_name=f"{(invoice_no.strip() or 'invoice')}.png",
        mime="image/png",
    )

with col_jpeg:
    st.download_button(
        label="Download JPEG",
        data=generate_invoice_jpeg(invoice_no.strip() or "N/A", invoice_date.strftime("%d-%b-%Y"), customer, selected_line_items, gst_enabled, gst_rate, owner_details, theme),
        file_name=f"{(invoice_no.strip() or 'invoice')}.jpg",
        mime="image/jpeg",
    )
