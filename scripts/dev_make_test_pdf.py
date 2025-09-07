from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

def page(c, y, lines):
    for i, t in enumerate(lines):
        c.drawString(72, y-16*i, t)

c = canvas.Canvas("output/smoke-test.pdf", pagesize=LETTER)
c.setFont("Helvetica", 11)

page(c, 700, [
 "WHITEPAPER: Fractal Tape as addressable memory.",
 "IDEA: Use temporal foveation to triage logs.",
 "DIRECTION: Build a quote-only compiler pipeline.",
])
c.showPage()
page(c, 700, [
 "IDEA: Broad-sweep chunking to cut token costs.",
 "DIRECTION: Batch by category × lead tag.",
])
c.save()
print("Wrote output/smoke-test.pdf")
