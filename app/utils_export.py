
from io import StringIO, BytesIO
from flask import Response
import csv

def stream_csv(filename, headers, rows):
    buf = StringIO()
    w = csv.writer(buf)
    if headers: w.writerow(headers)
    for r in rows:
        w.writerow(r)
    data = buf.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"} )

def stream_xlsx(filename, headers, rows):
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        if headers:
            ws.append(headers)
        for r in rows:
            ws.append(list(r))
        bio = BytesIO()
        wb.save(bio)
        return Response(bio.getvalue(),
                        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename={filename}"} )
    except Exception:
        return stream_csv(filename.replace(".xlsx", ".csv"), headers, rows)

def stream_pdf(filename, title, headers, rows):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        width, height = landscape(A4)

        y = height - 2*cm
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2*cm, y, title)
        y -= 0.8*cm

        c.setFont("Helvetica-Bold", 10)
        x = 2*cm
        col_width = (width - 4*cm) / max(len(headers) if headers else 1, 1)
        if headers:
            for h in headers:
                c.drawString(x, y, str(h)[:40])
                x += col_width
            y -= 0.6*cm

        c.setFont("Helvetica", 9)
        for row in rows:
            x = 2*cm
            if y < 2*cm:
                c.showPage()
                y = height - 2*cm
            for cell in row:
                c.drawString(x, y, str(cell)[:50])
                x += col_width
            y -= 0.5*cm

        c.showPage()
        c.save()
        pdf_data = buf.getvalue()
        return Response(pdf_data, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={filename}"} )
    except Exception:
        return stream_csv(filename.replace(".pdf", ".csv"), headers, rows)
