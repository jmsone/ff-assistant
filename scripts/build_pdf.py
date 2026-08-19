"""Printable draft cheatsheet PDF.

Reads output/cheatsheet.csv (produced by build_cheatsheet.py).
Emits output/cheatsheet.pdf:
  - Page 1: positional boards (QB/RB/WR/TE/K/DEF side-by-side)
  - Pages 2+: overall top 200 by VBD, tier-banded
Highlights (tiebreaker only): PHI team + Penn State college.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from src.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "output" / "cheatsheet.csv"
PDF_PATH = PROJECT_ROOT / "output" / "cheatsheet.pdf"

PAGE_W, PAGE_H = landscape(letter)  # 792 x 612
MARGIN = 0.35 * inch

EAGLES_TINT = colors.HexColor("#E4F0DC")   # subtle green
PSU_TINT = colors.HexColor("#DDE7F2")      # subtle blue
BOTH_TINT = colors.HexColor("#D3EBD5")     # both (rare)
HEADER_BG = colors.HexColor("#1F3A5F")
HEADER_FG = colors.white

TIER_SHADES = [
    colors.HexColor("#FFFFFF"),  # 0 unused
    colors.HexColor("#FFEBCC"),  # T1
    colors.HexColor("#FFF3D9"),
    colors.HexColor("#FFF9E6"),
    colors.HexColor("#F0F7FF"),
    colors.HexColor("#F5F5F5"),
    colors.HexColor("#FAFAFA"),
]


def tier_color(t) -> colors.Color:
    if pd.isna(t):
        return colors.white
    idx = min(int(t), len(TIER_SHADES) - 1)
    return TIER_SHADES[idx]


def row_tint(team: str, college: str) -> colors.Color | None:
    is_phi = str(team).upper() == "PHI"
    is_psu = "penn state" in str(college).lower() if college else False
    if is_phi and is_psu:
        return BOTH_TINT
    if is_phi:
        return EAGLES_TINT
    if is_psu:
        return PSU_TINT
    return None


def draw_header(c: canvas.Canvas, title: str, subtitle: str) -> float:
    c.setFillColor(HEADER_BG)
    c.rect(0, PAGE_H - 0.4 * inch, PAGE_W, 0.4 * inch, fill=1, stroke=0)
    c.setFillColor(HEADER_FG)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MARGIN, PAGE_H - 0.27 * inch, title)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.27 * inch, subtitle)
    return PAGE_H - 0.55 * inch  # y start for content


def draw_legend(c: canvas.Canvas, y: float) -> float:
    c.setFont("Helvetica", 7)
    x = MARGIN
    swatch_w = 0.14 * inch
    for label, color in [
        ("Eagles", EAGLES_TINT),
        ("Penn State", PSU_TINT),
        ("Tier 1", TIER_SHADES[1]),
        ("Tier 2", TIER_SHADES[2]),
    ]:
        c.setFillColor(color)
        c.rect(x, y - 0.02 * inch, swatch_w, 0.10 * inch, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.drawString(x + swatch_w + 2, y, label)
        x += swatch_w + 0.5 * inch
    return y - 0.15 * inch


def draw_positional_board(c: canvas.Canvas, df: pd.DataFrame, cfg) -> None:
    """Page 1: six columns for QB/RB/WR/TE/K/DEF."""
    positions = ["QB", "RB", "WR", "TE", "K", "DEF"]
    rows_per_col = {"QB": 24, "RB": 40, "WR": 40, "TE": 20, "K": 12, "DEF": 14}

    title = f"{cfg.name} {cfg.season} - Positional Boards"
    subtitle = f"{cfg.num_teams}-team | half-PPR | generated {date.today().isoformat()}"
    y_top = draw_header(c, title, subtitle)
    y_top = draw_legend(c, y_top - 0.10 * inch)

    col_gap = 0.05 * inch
    total_w = PAGE_W - 2 * MARGIN
    col_w = (total_w - col_gap * 5) / 6

    for i, pos in enumerate(positions):
        x = MARGIN + i * (col_w + col_gap)
        _draw_pos_column(c, df, pos, x, y_top, col_w, rows_per_col[pos])


def _draw_pos_column(c: canvas.Canvas, df: pd.DataFrame, pos: str,
                     x: float, y_top: float, w: float, max_rows: int) -> None:
    sub = df[df["position"] == pos].sort_values("overall_rank").head(max_rows)

    # Column header
    hdr_h = 0.20 * inch
    c.setFillColor(HEADER_BG)
    c.rect(x, y_top - hdr_h, w, hdr_h, fill=1, stroke=0)
    c.setFillColor(HEADER_FG)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 3, y_top - hdr_h + 5, pos)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(x + w - 3, y_top - hdr_h + 5, "#  Name  Tm/Bye  T  VBD  ADP")

    # Rows
    row_h = 0.145 * inch
    y = y_top - hdr_h
    for _, row in sub.iterrows():
        y -= row_h
        tint = row_tint(row.get("team", ""), row.get("college", ""))
        tier = row.get("tier")
        bg = tint if tint is not None else tier_color(tier)
        c.setFillColor(bg)
        c.rect(x, y, w, row_h, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#DDDDDD"))
        c.setLineWidth(0.3)
        c.line(x, y, x + w, y)

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 6.5)
        # pos_rank
        c.drawString(x + 2, y + 3, f"{int(row['pos_rank'])}")
        # name (truncated)
        name = str(row["name"])[:18]
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 15, y + 3, name)
        # team/bye
        c.setFont("Helvetica", 6)
        tm = str(row.get("team", ""))[:3]
        bye = row.get("bye")
        bye_s = f"{int(bye)}" if pd.notna(bye) else "-"
        c.drawString(x + w - 65, y + 3, f"{tm} b{bye_s}")
        # tier
        c.setFont("Helvetica-Bold", 6)
        c.drawString(x + w - 40, y + 3, f"T{int(tier) if pd.notna(tier) else '-'}")
        # VBD
        c.setFont("Helvetica", 6)
        vbd = row.get("vbd", 0)
        c.drawString(x + w - 28, y + 3, f"{vbd:.0f}")
        # ADP
        adp = row.get("adp")
        adp_s = f"{adp:.0f}" if pd.notna(adp) else "-"
        c.drawRightString(x + w - 2, y + 3, adp_s)

    # Column border
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(0.5)
    c.rect(x, y, w, y_top - y, fill=0, stroke=1)


def draw_overall_pages(c: canvas.Canvas, df: pd.DataFrame, cfg,
                       n_players: int = 200) -> None:
    """Overall top-N by VBD, tier-banded, multi-column across pages."""
    top = df.sort_values("overall_rank").head(n_players).reset_index(drop=True)

    rows_per_col = 55
    cols_per_page = 3
    per_page = rows_per_col * cols_per_page

    total_w = PAGE_W - 2 * MARGIN
    col_gap = 0.10 * inch
    col_w = (total_w - col_gap * (cols_per_page - 1)) / cols_per_page

    page_num = 0
    idx = 0
    while idx < len(top):
        page_num += 1
        c.showPage()
        title = f"{cfg.name} {cfg.season} - Overall Top {n_players} (by VBD)"
        subtitle = f"Page {page_num} | {date.today().isoformat()}"
        y_top = draw_header(c, title, subtitle)
        y_top = draw_legend(c, y_top - 0.10 * inch)

        page_end = min(idx + per_page, len(top))
        page_rows = top.iloc[idx:page_end]

        for ci in range(cols_per_page):
            x = MARGIN + ci * (col_w + col_gap)
            col_slice = page_rows.iloc[ci * rows_per_col : (ci + 1) * rows_per_col]
            _draw_overall_column(c, col_slice, x, y_top, col_w)

        idx = page_end


def _draw_overall_column(c: canvas.Canvas, sub: pd.DataFrame,
                         x: float, y_top: float, w: float) -> None:
    # Column header
    hdr_h = 0.18 * inch
    c.setFillColor(HEADER_BG)
    c.rect(x, y_top - hdr_h, w, hdr_h, fill=1, stroke=0)
    c.setFillColor(HEADER_FG)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 2, y_top - hdr_h + 4, "#   Player           Pos  Tm  By  T   VBD   ADP  SoS")

    row_h = 0.145 * inch
    y = y_top - hdr_h
    for _, row in sub.iterrows():
        y -= row_h
        tint = row_tint(row.get("team", ""), row.get("college", ""))
        tier = row.get("tier")
        bg = tint if tint is not None else tier_color(tier)
        c.setFillColor(bg)
        c.rect(x, y, w, row_h, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#DDDDDD"))
        c.setLineWidth(0.3)
        c.line(x, y, x + w, y)

        c.setFillColor(colors.black)
        # rank
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 2, y + 3, f"{int(row['overall_rank'])}")
        # name
        name = str(row["name"])[:18]
        c.drawString(x + 22, y + 3, name)
        # pos
        c.setFont("Helvetica", 6.5)
        pos_s = f"{row['position']}{int(row['pos_rank'])}"
        c.drawString(x + 118, y + 3, pos_s)
        # team
        c.drawString(x + 140, y + 3, str(row.get("team", ""))[:3])
        # bye
        bye = row.get("bye")
        c.drawString(x + 158, y + 3, f"{int(bye)}" if pd.notna(bye) else "-")
        # tier
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x + 173, y + 3, f"{int(tier) if pd.notna(tier) else '-'}")
        # vbd
        c.setFont("Helvetica", 6.5)
        vbd = row.get("vbd", 0)
        c.drawString(x + 186, y + 3, f"{vbd:.0f}")
        # adp
        adp = row.get("adp")
        adp_s = f"{adp:.0f}" if pd.notna(adp) else "-"
        c.drawString(x + 210, y + 3, adp_s)
        # sos grade
        sos = row.get("sos_grade", "")
        c.drawString(x + 230, y + 3, str(sos) if pd.notna(sos) else "-")

    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(0.5)
    c.rect(x, y, w, y_top - y, fill=0, stroke=1)


def main() -> None:
    cfg = load_config()
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing {CSV_PATH}. Run build_cheatsheet.py first.")

    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df)} players from {CSV_PATH}")

    c = canvas.Canvas(str(PDF_PATH), pagesize=landscape(letter))
    c.setTitle(f"{cfg.name} {cfg.season} Draft Cheatsheet")

    draw_positional_board(c, df, cfg)
    draw_overall_pages(c, df, cfg, n_players=200)

    c.save()
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
