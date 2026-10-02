#!/usr/bin/env python3
"""
IceStream Presentation Generator
Generates an ultra-premium, eye-catchy 16:9 widescreen PowerPoint presentation (PPTX)
for the IceStream Lakehouse Observability & Self-Healing Data Pipeline platform.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# --- Color Palette ---
COLOR_BG_DARK = RGBColor(10, 15, 29)         # #0A0F1D Deep Obsidian
COLOR_CARD_BG = RGBColor(19, 27, 46)         # #131B2E Navy Card Surface
COLOR_CARD_BORDER = RGBColor(30, 41, 69)     # #1E2945 Subtle Border
COLOR_ACCENT_CYAN = RGBColor(0, 229, 255)    # #00E5FF Neon Electric Cyan
COLOR_ACCENT_BLUE = RGBColor(56, 189, 248)   # #38BDF8 Radiant Sky Ice
COLOR_ACCENT_GREEN = RGBColor(16, 185, 129)  # #10B981 Emerald Green / Healthy
COLOR_ACCENT_AMBER = RGBColor(245, 158, 11)  # #F59E0B Warning Amber
COLOR_ACCENT_RED = RGBColor(239, 68, 68)     # #EF4444 Circuit Breaker Red
COLOR_ACCENT_PURPLE = RGBColor(139, 92, 246) # #8B5CF6 Deep Violet
COLOR_TEXT_WHITE = RGBColor(255, 255, 255)   # #FFFFFF Crisp White
COLOR_TEXT_MUTED = RGBColor(148, 163, 184)   # #94A3B8 Slate Gray
COLOR_TEXT_DIM = RGBColor(100, 116, 139)     # #64748B Dim Slate

FONT_HEADING = "Trebuchet MS"
FONT_BODY = "Calibri"

TOTAL_SLIDES = 12
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

ASSET_DIR = "/Users/sujal/Desktop/IceStream/docs/presentation_assets"
HERO_IMG = os.path.join(ASSET_DIR, "icestream_hero_1790858115206.jpg")
OBS_IMG = os.path.join(ASSET_DIR, "icestream_observability_1790858162230.jpg")
LAKEHOUSE_IMG = os.path.join(ASSET_DIR, "icestream_lakehouse_1790858186325.jpg")


def create_presentation():
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    blank_layout = prs.slide_layouts[6]  # Blank slide

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================
    def set_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT)
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_BG_DARK
        bg.line.fill.background()
        return bg

    def add_footer(slide, slide_num):
        # Footer divider line
        divider = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.8), Inches(6.95), Inches(11.733), Inches(0.015)
        )
        divider.fill.solid()
        divider.fill.fore_color.rgb = RGBColor(24, 33, 56)
        divider.line.fill.background()

        # Left label
        tb_left = slide.shapes.add_textbox(Inches(0.8), Inches(7.0), Inches(8.0), Inches(0.35))
        tf_left = tb_left.text_frame
        tf_left.word_wrap = True
        p_left = tf_left.paragraphs[0]
        p_left.text = "ICESTREAM  |  Real-Time Lakehouse Observability & Autonomous Self-Healing Pipeline"
        p_left.font.name = FONT_BODY
        p_left.font.size = Pt(9)
        p_left.font.color.rgb = COLOR_TEXT_DIM

        # Right slide number
        tb_right = slide.shapes.add_textbox(Inches(10.5), Inches(7.0), Inches(2.0), Inches(0.35))
        tf_right = tb_right.text_frame
        p_right = tf_right.paragraphs[0]
        p_right.alignment = PP_ALIGN.RIGHT
        p_right.text = f"{slide_num:02d} / {TOTAL_SLIDES:02d}"
        p_right.font.name = FONT_BODY
        p_right.font.size = Pt(9)
        p_right.font.bold = True
        p_right.font.color.rgb = COLOR_ACCENT_CYAN

    def add_header(slide, badge_text, title_text, subtitle_text, accent_color=COLOR_ACCENT_CYAN):
        # Badge Pill
        badge_box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.8), Inches(0.42), Inches(2.6), Inches(0.32)
        )
        badge_box.fill.solid()
        badge_box.fill.fore_color.rgb = RGBColor(16, 26, 48)
        badge_box.line.color.rgb = accent_color
        badge_box.line.width = Pt(1)
        p_b = badge_box.text_frame.paragraphs[0]
        p_b.alignment = PP_ALIGN.CENTER
        p_b.text = badge_text.upper()
        p_b.font.name = FONT_HEADING
        p_b.font.size = Pt(9.5)
        p_b.font.bold = True
        p_b.font.color.rgb = accent_color

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.78), Inches(11.733), Inches(0.65))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p_t = tf.paragraphs[0]
        p_t.text = title_text
        p_t.font.name = FONT_HEADING
        p_t.font.size = Pt(24)
        p_t.font.bold = True
        p_t.font.color.rgb = COLOR_TEXT_WHITE

        # Subtitle
        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.42), Inches(11.733), Inches(0.4))
        tf_s = sub_box.text_frame
        tf_s.word_wrap = True
        tf_s.margin_left = tf_s.margin_top = tf_s.margin_right = tf_s.margin_bottom = 0
        p_s = tf_s.paragraphs[0]
        p_s.text = subtitle_text
        p_s.font.name = FONT_BODY
        p_s.font.size = Pt(12)
        p_s.font.color.rgb = COLOR_TEXT_MUTED

    def add_card(slide, left, top, width, height, title, bullet_items, accent_color=COLOR_ACCENT_CYAN, icon="◆"):
        # Card background
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            left, top, width, height
        )
        card.fill.solid()
        card.fill.fore_color.rgb = COLOR_CARD_BG
        card.line.color.rgb = COLOR_CARD_BORDER
        card.line.width = Pt(1)

        # Accent top stripe
        stripe = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            left + Inches(0.15), top, width - Inches(0.3), Inches(0.04)
        )
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = accent_color
        stripe.line.fill.background()

        # Text Frame
        tb = slide.shapes.add_textbox(
            left + Inches(0.25), top + Inches(0.18), width - Inches(0.5), height - Inches(0.3)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        # Title
        p_title = tf.paragraphs[0]
        p_title.text = f"{icon}  {title}"
        p_title.font.name = FONT_HEADING
        p_title.font.size = Pt(13.5)
        p_title.font.bold = True
        p_title.font.color.rgb = accent_color
        p_title.space_after = Pt(8)

        # Bullets
        for idx, item in enumerate(bullet_items):
            p = tf.add_paragraph()
            p.text = item
            p.font.name = FONT_BODY
            p.font.size = Pt(10.5)
            p.font.color.rgb = COLOR_TEXT_MUTED
            p.space_after = Pt(5)

    def add_metric_callout(slide, left, top, width, height, value, label, subtext, accent_color=COLOR_ACCENT_CYAN):
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            left, top, width, height
        )
        card.fill.solid()
        card.fill.fore_color.rgb = COLOR_CARD_BG
        card.line.color.rgb = accent_color
        card.line.width = Pt(1.2)

        tb = slide.shapes.add_textbox(left + Inches(0.15), top + Inches(0.12), width - Inches(0.3), height - Inches(0.24))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p_val = tf.paragraphs[0]
        p_val.alignment = PP_ALIGN.CENTER
        p_val.text = value
        p_val.font.name = FONT_HEADING
        p_val.font.size = Pt(30)
        p_val.font.bold = True
        p_val.font.color.rgb = accent_color

        p_lbl = tf.add_paragraph()
        p_lbl.alignment = PP_ALIGN.CENTER
        p_lbl.text = label.upper()
        p_lbl.font.name = FONT_HEADING
        p_lbl.font.size = Pt(10)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = COLOR_TEXT_WHITE
        p_lbl.space_after = Pt(2)

        p_sub = tf.add_paragraph()
        p_sub.alignment = PP_ALIGN.CENTER
        p_sub.text = subtext
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(8.5)
        p_sub.font.color.rgb = COLOR_TEXT_MUTED

    # =========================================================================
    # SLIDE 1: HERO / TITLE SLIDE
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_background(slide1)

    # Insert Hero Artwork on right
    if os.path.exists(HERO_IMG):
        slide1.shapes.add_picture(
            HERO_IMG,
            Inches(6.2), Inches(0.8), Inches(6.4), Inches(5.8)
        )
        # Subtle framing border around hero image
        hero_border = slide1.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(6.2), Inches(0.8), Inches(6.4), Inches(5.8)
        )
        hero_border.fill.background()
        hero_border.line.color.rgb = COLOR_ACCENT_CYAN
        hero_border.line.width = Pt(1.5)

    # Title content on left
    # Pill
    badge1 = slide1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(1.1), Inches(3.4), Inches(0.36)
    )
    badge1.fill.solid()
    badge1.fill.fore_color.rgb = RGBColor(16, 26, 48)
    badge1.line.color.rgb = COLOR_ACCENT_CYAN
    badge1.line.width = Pt(1)
    p_b1 = badge1.text_frame.paragraphs[0]
    p_b1.alignment = PP_ALIGN.CENTER
    p_b1.text = "ENTERPRISE STREAMING PLATFORM"
    p_b1.font.name = FONT_HEADING
    p_b1.font.size = Pt(10)
    p_b1.font.bold = True
    p_b1.font.color.rgb = COLOR_ACCENT_CYAN

    # Main Brand
    tb1_brand = slide1.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(5.2), Inches(1.2))
    tf1_b = tb1_brand.text_frame
    tf1_b.word_wrap = True
    p1_b = tf1_b.paragraphs[0]
    p1_b.text = "ICESTREAM"
    p1_b.font.name = FONT_HEADING
    p1_b.font.size = Pt(46)
    p1_b.font.bold = True
    p1_b.font.color.rgb = COLOR_TEXT_WHITE

    # Subtitle
    tb1_sub = slide1.shapes.add_textbox(Inches(0.8), Inches(2.8), Inches(5.1), Inches(1.4))
    tf1_s = tb1_sub.text_frame
    tf1_s.word_wrap = True
    p1_s = tf1_s.paragraphs[0]
    p1_s.text = "Real-Time Lakehouse Observability & Autonomous Self-Healing Data Pipeline"
    p1_s.font.name = FONT_HEADING
    p1_s.font.size = Pt(17)
    p1_s.font.bold = True
    p1_s.font.color.rgb = COLOR_ACCENT_BLUE

    p1_desc = tf1_s.add_paragraph()
    p1_desc.text = "Eliminating silent data corruption in mission-critical streaming pipelines with real-time circuit breakers, Apache Iceberg ACID isolation, and closed-loop automated remediation."
    p1_desc.font.name = FONT_BODY
    p1_desc.font.size = Pt(11.5)
    p1_desc.font.color.rgb = COLOR_TEXT_MUTED
    p1_desc.space_before = Pt(8)

    # 3 Highlights Tags
    tags = [
        ("PHASE 7 VERIFIED", COLOR_ACCENT_GREEN),
        ("APACHE ICEBERG v2", COLOR_ACCENT_CYAN),
        ("KAFKA + FLINK HA", COLOR_ACCENT_PURPLE),
    ]
    for idx, (tag_text, tag_col) in enumerate(tags):
        tag_box = slide1.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.8 + idx * 1.7), Inches(5.2), Inches(1.58), Inches(0.38)
        )
        tag_box.fill.solid()
        tag_box.fill.fore_color.rgb = COLOR_CARD_BG
        tag_box.line.color.rgb = tag_col
        tag_box.line.width = Pt(1)
        p_tag = tag_box.text_frame.paragraphs[0]
        p_tag.alignment = PP_ALIGN.CENTER
        p_tag.text = tag_text
        p_tag.font.name = FONT_HEADING
        p_tag.font.size = Pt(9)
        p_tag.font.bold = True
        p_tag.font.color.rgb = tag_col

    add_footer(slide1, 1)

    # =========================================================================
    # SLIDE 2: THE PROBLEM (SILENT DATA CORRUPTION)
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_background(slide2)
    add_header(
        slide2,
        "The Industry Crisis",
        "The High-Velocity Data Dilemma: Fast, Dirty & Silent",
        "Modern lakehouses ingest millions of events per second, but silent anomalies corrupt downstream intelligence before teams notice.",
        COLOR_ACCENT_RED
    )

    card_w = Inches(3.68)
    card_h = Inches(3.9)
    top_pos = Inches(2.05)

    add_card(
        slide2, Inches(0.8), top_pos, card_w, card_h,
        "Silent Data Poisoning",
        [
            "• Malformed JSON payloads bypass naive ingestion filters without throwing crash exceptions.",
            "• Subtle schema drift, negative monetary amounts, and null IDs slip through untyped streaming topics.",
            "• Micro-anomalies compound across transformations, accumulating undetected in Bronze/Silver lake layers."
        ],
        COLOR_ACCENT_RED,
        icon="⚠"
    )

    add_card(
        slide2, Inches(4.82), top_pos, card_w, card_h,
        "Downstream Contamination",
        [
            "• Tainted events propagate to executive BI dashboards, ML model feature stores, and financial ledgers.",
            "• Erroneous analytics lead to incorrect automated pricing, invalid billing runs, and regulatory non-compliance.",
            "• Trust in enterprise data pipelines is eroded; analysts spend 60% of their time investigating bad data."
        ],
        COLOR_ACCENT_AMBER,
        icon="⚡"
    )

    add_card(
        slide2, Inches(8.85), top_pos, card_w, card_h,
        "The 3:00 AM MTTR Nightmare",
        [
            "• Mean Time to Detect (MTTD) often exceeds 24-48 hours; Mean Time to Recover (MTTR) takes 4-8 hours.",
            "• Manual firefighting: grep server logs, stop consumers, write bespoke backfill scripts, rerun batch jobs.",
            "• High operational cost, developer burnout, and persistent fear of deploying upstream schema updates."
        ],
        COLOR_ACCENT_PURPLE,
        icon="⏱"
    )

    # Bottom Quote Banner
    banner = slide2.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(6.12), Inches(11.733), Inches(0.68)
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = RGBColor(22, 18, 30)
    banner.line.color.rgb = COLOR_ACCENT_RED
    banner.line.width = Pt(1)
    p_ban = banner.text_frame.paragraphs[0]
    p_ban.alignment = PP_ALIGN.CENTER
    p_ban.text = "CORE REALITY: By the time an analyst flags an invalid revenue aggregate in Tableau, millions of corrupt records have permanently mutated the lake."
    p_ban.font.name = FONT_BODY
    p_ban.font.size = Pt(10.5)
    p_ban.font.bold = True
    p_ban.font.color.rgb = COLOR_TEXT_WHITE

    add_footer(slide2, 2)

    # =========================================================================
    # SLIDE 3: THE SOLUTION / PARADIGM SHIFT
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_background(slide3)
    add_header(
        slide3,
        "The Paradigm Shift",
        "The IceStream Solution: An Autonomous Immune System",
        "IceStream establishes a real-time, zero-trust quality gate that isolates anomalies, prevents contamination, and auto-heals pipelines.",
        COLOR_ACCENT_GREEN
    )

    col_w = Inches(3.68)
    col_h = Inches(3.3)
    top_pos3 = Inches(2.05)

    add_card(
        slide3, Inches(0.8), top_pos3, col_w, col_h,
        "In-Stream Quality Gate",
        [
            "• Continuous, sub-millisecond evaluation of 100% of event payloads in real time.",
            "• 7-Vector Anomaly Detection + dynamic Schema Drift validation against versioned contracts.",
            "• Zero false positives; low-cardinality metrics aggregated continuously in sliding windows."
        ],
        COLOR_ACCENT_CYAN,
        icon="🛡"
    )

    add_card(
        slide3, Inches(4.82), top_pos3, col_w, col_h,
        "Dynamic Circuit Breaker",
        [
            "• Authoritative state machine trips pipeline when rolling error rate crosses 2% critical threshold.",
            "• Instantly prevents bad events from corrupting downstream Apache Iceberg Silver & Gold tables.",
            "• Half-Open probe mechanism safely verifies source recovery before automated resumption."
        ],
        COLOR_ACCENT_AMBER,
        icon="⚙"
    )

    add_card(
        slide3, Inches(8.85), top_pos3, col_w, col_h,
        "Autonomous Remediation",
        [
            "• Corrupted events routed to an isolated Apache Iceberg Dead Letter Queue (DLQ) with raw payload.",
            "• Automated 11-state remediation engine triggers re-fetching, re-validating, and re-processing.",
            "• Resolves incidents in < 30 seconds with complete Slack notifications and audit provenance."
        ],
        COLOR_ACCENT_GREEN,
        icon="✨"
    )

    # 4 Bottom Metric Callouts
    met_w = Inches(2.78)
    met_h = Inches(1.3)
    top_met = Inches(5.5)

    add_metric_callout(slide3, Inches(0.8), top_met, met_w, met_h, "0%", "Silent Corruption", "100% of in-stream events validated", COLOR_ACCENT_CYAN)
    add_metric_callout(slide3, Inches(3.78), top_met, met_w, met_h, "2.0%", "Critical Trip Limit", "Dynamic rolling-window threshold", COLOR_ACCENT_AMBER)
    add_metric_callout(slide3, Inches(6.76), top_met, met_w, met_h, "< 30s", "Automated MTTR", "Autonomous refetch & self-healing", COLOR_ACCENT_GREEN)
    add_metric_callout(slide3, Inches(9.74), top_met, met_w, met_h, "100%", "ACID Concurrency", "Zero uncommitted dirty reads", COLOR_ACCENT_PURPLE)

    add_footer(slide3, 3)

    # =========================================================================
    # SLIDE 4: END-TO-END ARCHITECTURE
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_background(slide4)
    add_header(
        slide4,
        "System Blueprint",
        "End-to-End Enterprise Architecture: Ingestion to Lakehouse",
        "A decoupled, fault-tolerant topology connecting high-throughput messaging, streaming compute, ACID lakehouse, and observability.",
        COLOR_ACCENT_CYAN
    )

    # 5 Flow Columns
    steps = [
        ("1. INGESTION", "Kafka KRaft", [
            "• 6 Core Event Topics",
            "• 1,000+ events/sec",
            "• KRaft Quorum (No ZK)",
            "• RF=3 Partition HA",
            "• Schema validation topic"
        ], COLOR_ACCENT_BLUE),
        ("2. STREAM ENGINE", "Apache Flink 1.18", [
            "• Stateful Stream Joins",
            "• Exactly-Once 2PC",
            "• 10s Checkpoint Barriers",
            "• RocksDB State Backend",
            "• S3 Commit Coordination"
        ], COLOR_ACCENT_PURPLE),
        ("3. QUALITY ENGINE", "Dual Engine", [
            "• 7-Vector Anomaly Engine",
            "• Schema Drift Engine",
            "• Great Expectations GE",
            "• 1m / 5m Rolling Window",
            "• Circuit Breaker FSM"
        ], COLOR_ACCENT_CYAN),
        ("4. LAKEHOUSE", "Apache Iceberg", [
            "• REST Catalog on S3",
            "• Bronze Raw Table",
            "• Silver Curated Table",
            "• Parquet DLQ Quarantine",
            "• Auto Parquet Compactor"
        ], COLOR_ACCENT_GREEN),
        ("5. CONTROL PLANE", "FastAPI & React", [
            "• Asynchronous REST API",
            "• React Flow Lineage DAG",
            "• Node Diagnostic Engine",
            "• Slack Webhook Alerts",
            "• Prometheus / Grafana"
        ], COLOR_ACCENT_AMBER),
    ]

    col_width_5 = Inches(2.23)
    col_gap_5 = Inches(0.14)
    top_pos4 = Inches(2.1)
    card_h4 = Inches(4.5)

    for idx, (step_num, step_title, bullets, acc_col) in enumerate(steps):
        left_coord = Inches(0.8) + idx * (col_width_5 + col_gap_5)
        add_card(
            slide4, left_coord, top_pos4, col_width_5, card_h4,
            f"{step_num}\n{step_title}",
            bullets,
            acc_col,
            icon="▶"
        )

    add_footer(slide4, 4)

    # =========================================================================
    # SLIDE 5: QUALITY ENGINE DEEP DIVE
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_background(slide5)
    add_header(
        slide5,
        "Data Integrity Engine",
        "Deep Dive: Multi-Vector Quality & Schema Drift Detection",
        "Combining ultra-fast custom streaming validation with enterprise declarative Great Expectations suites.",
        COLOR_ACCENT_CYAN
    )

    card_w5 = Inches(5.7)
    card_h5 = Inches(4.65)
    top_pos5 = Inches(2.05)

    add_card(
        slide5, Inches(0.8), top_pos5, card_w5, card_h5,
        "7 In-Stream Anomaly Detectors",
        [
            "• Null & Required Field Validation: Enforces mandatory fields like customer_id, order_id, amount without exception crashes.",
            "• Positive Amount Verification: Rejects negative payments or impossible micro-transactions; validates currency domains (USD, EUR, GBP).",
            "• Impossible Amount Bounds: Detects extreme billing anomalies and outlier transaction values outside expected limits.",
            "• Future Timestamp & Lateness Tolerances: Rejects events with clocks skewed into the future or stale late records.",
            "• Rolling Deduplication Engine: Bounded state deduplication against duplicate event_ids and repeated order transactions.",
            "• Dynamic Severity Classification: Categorizes rule failures into CRITICAL, HIGH, MEDIUM, and LOW tiers for granular action."
        ],
        COLOR_ACCENT_CYAN,
        icon="⚡"
    )

    add_card(
        slide5, Inches(6.8), top_pos5, card_w5, card_h5,
        "Schema Drift & Hybrid Great Expectations",
        [
            "• Zero-I/O Dynamic Schema Comparator: Evaluates payload structures against cached JSON Schema contracts (v1, v2, v3) in < 0.4 ms.",
            "• Granular Change Taxonomy: Categorizes NEW_COLUMN, MISSING_COLUMN, TYPE_CHANGE, and RENAMED_COLUMN evolutions.",
            "• Compatibility Engine: Evaluates evolutions as COMPATIBLE, WARNING, or BREAKING with actionable remediation hints.",
            "• Great Expectations (v0.18) Adapter: Maps declarative enterprise expectations to standardized streaming ValidationResult models.",
            "• Deduplicated Aggregation: Multiple rule violations on a single event are aggregated into 1 failed record to prevent error over-counting.",
            "• Low-Cardinality Telemetry: Emits real-time Prometheus counters for pass/fail ratios and rule violation distributions."
        ],
        COLOR_ACCENT_PURPLE,
        icon="🧬"
    )

    add_footer(slide5, 5)

    # =========================================================================
    # SLIDE 6: AUTONOMOUS SELF-HEALING & CIRCUIT BREAKER
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_background(slide6)
    add_header(
        slide6,
        "Autonomous Remediation",
        "Dynamic Circuit Breaker & 11-State Self-Healing Pipeline",
        "Moving data engineering from passive Slack alerts to closed-loop, automated failure isolation and self-healing.",
        COLOR_ACCENT_AMBER
    )

    # Left Column: FSM State Flow
    fsm_w = Inches(6.8)
    fsm_h = Inches(4.65)
    add_card(
        slide6, Inches(0.8), Inches(2.05), fsm_w, fsm_h,
        "The 11-State Self-Healing State Machine",
        [
            "• [RUNNING] Healthy baseline: Error rate < 1.0% in 1m & 5m rolling windows.",
            "• [DEGRADED] Warning threshold crossed (1.0% - 2.0% error rate). Telemetry alerts emitted.",
            "• [CIRCUIT_OPEN] Critical threshold breached (> 2.0%). Pipeline ingestion tripped automatically.",
            "• [QUARANTINING] Corrupted events isolated to Apache Iceberg DLQ; Silver stream paused.",
            "• [REMEDIATING] Autonomous remediation controller takes thread-safe idempotency lock.",
            "• [REFETCHING] Re-fetches clean payloads from upstream source adapters using provenance IDs.",
            "• [REPROCESSING] Re-runs Quality Engine against re-fetched events to guarantee cleanliness.",
            "• [VALIDATING] Confirms zero violations across batch; routes remaining bad data to quarantine.",
            "• [RESUMING] Half-Open probe verifies source stability before full traffic resumption.",
            "• [RECOVERED] Pipeline restored to RUNNING; incident automatically marked RESOLVED in DB & Slack."
        ],
        COLOR_ACCENT_AMBER,
        icon="🔄"
    )

    # Right Column: 3 Key Pillars
    r_w = Inches(4.6)
    add_card(
        slide6, Inches(7.9), Inches(2.05), r_w, Inches(1.4),
        "Dynamic Error-Rate Engine",
        [
            "• Calculates real-time failure ratio: invalid_events / total_events.",
            "• 1-min & 5-min dual rolling windows prevent jitter."
        ],
        COLOR_ACCENT_CYAN,
        icon="📊"
    )

    add_card(
        slide6, Inches(7.9), Inches(3.6), r_w, Inches(1.4),
        "Half-Open Recovery Probe",
        [
            "• Single-probe recovery protects against flapping pipelines.",
            "• Requires verified zero errors before full circuit closure."
        ],
        COLOR_ACCENT_GREEN,
        icon="🔒"
    )

    add_card(
        slide6, Inches(7.9), Inches(5.15), r_w, Inches(1.55),
        "Idempotent Concurrency Lock",
        [
            "• PostgreSQL-backed state manager with SQLite fallback.",
            "• Exponential backoff (3 attempts max) prevents retry storms."
        ],
        COLOR_ACCENT_PURPLE,
        icon="🛡"
    )

    add_footer(slide6, 6)

    # =========================================================================
    # SLIDE 7: APACHE ICEBERG LAKEHOUSE & ACID AUDIT (WITH 3D ARTWORK)
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_background(slide7)
    add_header(
        slide7,
        "Lakehouse Storage",
        "Apache Iceberg Lakehouse: Multi-Tiered ACID Architecture",
        "Stateless REST catalog, snapshot isolation, and elimination of the streaming small-file problem.",
        COLOR_ACCENT_CYAN
    )

    # Left: Lakehouse 3D Artwork
    if os.path.exists(LAKEHOUSE_IMG):
        slide7.shapes.add_picture(
            LAKEHOUSE_IMG,
            Inches(0.8), Inches(2.05), Inches(5.9), Inches(4.65)
        )
        lh_border = slide7.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.8), Inches(2.05), Inches(5.9), Inches(4.65)
        )
        lh_border.fill.background()
        lh_border.line.color.rgb = COLOR_ACCENT_CYAN
        lh_border.line.width = Pt(1.5)

    # Right: Technical Architecture Cards
    right_w = Inches(5.5)
    add_card(
        slide7, Inches(7.0), Inches(2.05), right_w, Inches(1.45),
        "Multi-Tiered Data Separation",
        [
            "• Bronze: Raw immutable event log preserving full payload history.",
            "• Silver: Validated, deduplicated, schema-enforced curated table.",
            "• Quarantine: ACID Dead Letter Queue storing raw corrupted events."
        ],
        COLOR_ACCENT_CYAN,
        icon="📂"
    )

    add_card(
        slide7, Inches(7.0), Inches(3.65), right_w, Inches(1.45),
        "Optimistic Concurrency Control (OCC)",
        [
            "• Readers never block writers: Snapshot isolation guarantees zero locks.",
            "• Atomic Pointer Swaps: REST Catalog commits snapshots atomically.",
            "• Durability: Empirically audited under 500 concurrent write collisions."
        ],
        COLOR_ACCENT_GREEN,
        icon="⚡"
    )

    add_card(
        slide7, Inches(7.0), Inches(5.25), right_w, Inches(1.45),
        "Elimination of Small-File Problem",
        [
            "• 10s Flink checkpoint alignment prevents micro-parquet explosion.",
            "• Micro-batch QuarantineWriter (50-event / 5s buffer) protects S3 IOPS.",
            "• Background compaction merges small files into 128 MB blocks."
        ],
        COLOR_ACCENT_AMBER,
        icon="🗜"
    )

    add_footer(slide7, 7)

    # =========================================================================
    # SLIDE 8: OBSERVABILITY & LINEAGE DASHBOARD (WITH UI ARTWORK)
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    set_background(slide8)
    add_header(
        slide8,
        "Command & Control",
        "Full-Stack Observability & Interactive Lineage Dashboard",
        "React Flow interactive topology, node diagnostics, real-time telemetry curves, and Slack incident management.",
        COLOR_ACCENT_CYAN
    )

    # Left: Observability Dashboard Artwork
    if os.path.exists(OBS_IMG):
        slide8.shapes.add_picture(
            OBS_IMG,
            Inches(0.8), Inches(2.05), Inches(5.9), Inches(4.65)
        )
        obs_border = slide8.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.8), Inches(2.05), Inches(5.9), Inches(4.65)
        )
        obs_border.fill.background()
        obs_border.line.color.rgb = COLOR_ACCENT_CYAN
        obs_border.line.width = Pt(1.5)

    # Right: Dashboard Capabilities
    right_w8 = Inches(5.5)
    add_card(
        slide8, Inches(7.0), Inches(2.05), right_w8, Inches(1.45),
        "React Flow Interactive DAG",
        [
            "• Live topology visualization mapping data flow across Kafka, Flink, Quality Engine, Iceberg, and DLQ.",
            "• Dynamic status badges reflecting all 12 backend pipeline states."
        ],
        COLOR_ACCENT_CYAN,
        icon="🗺"
    )

    add_card(
        slide8, Inches(7.0), Inches(3.65), right_w8, Inches(1.45),
        "'Why is this node red?' Diagnostics",
        [
            "• 1-click root cause inspection on degraded or circuit-open nodes.",
            "• Instant breakdown of top failing rules, error rates, and active incidents.",
            "• Direct links to trigger autonomous remediation or pause pipeline."
        ],
        COLOR_ACCENT_RED,
        icon="🔍"
    )

    add_card(
        slide8, Inches(7.0), Inches(5.25), right_w8, Inches(1.45),
        "Slack Lifecycle & Incident Resolution",
        [
            "• Automated deterministic incident generation (INC-YYYY-MMDD-XXXX).",
            "• 3x exponential backoff Slack alerts with thread correlation.",
            "• In-app Acknowledge and Resolve actions backed by PostgreSQL."
        ],
        COLOR_ACCENT_PURPLE,
        icon="🔔"
    )

    add_footer(slide8, 8)

    # =========================================================================
    # SLIDE 9: HIGH AVAILABILITY & ENTERPRISE RESILIENCE
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    set_background(slide9)
    add_header(
        slide9,
        "Infrastructure Resilience",
        "Mission-Critical High Availability (HA) & Failover",
        "Engineered for zero data loss, multi-node clustering, and graceful automated failover.",
        COLOR_ACCENT_PURPLE
    )

    ha_w = Inches(5.7)
    ha_h = Inches(2.15)

    add_card(
        slide9, Inches(0.8), Inches(2.05), ha_w, ha_h,
        "3-Broker Kafka KRaft Quorum",
        [
            "• KRaft consensus replaces ZooKeeper; zero metadata latency spikes.",
            "• Topics configured with Replication Factor 3 and Min.ISR = 2.",
            "• Guarantees zero data loss even during an abrupt broker crash."
        ],
        COLOR_ACCENT_BLUE,
        icon="📡"
    )

    add_card(
        slide9, Inches(6.8), Inches(2.05), ha_w, ha_h,
        "Dual Flink JobManagers with HA",
        [
            "• Active-Standby JobManager architecture with automatic leader election.",
            "• Continuous state checkpointing to S3 MinIO storage.",
            "• Standby JobManager restores consumer offsets in < 5 seconds."
        ],
        COLOR_ACCENT_PURPLE,
        icon="⚡"
    )

    add_card(
        slide9, Inches(0.8), Inches(4.45), ha_w, ha_h,
        "Load-Balanced Backend Cluster",
        [
            "• Multi-worker FastAPI processes behind an Nginx reverse proxy.",
            "• Authoritative state stored in PostgreSQL with resilient SQLite fallback.",
            "• State-modifying endpoints secured by Bearer token authentication."
        ],
        COLOR_ACCENT_CYAN,
        icon="🌐"
    )

    add_card(
        slide9, Inches(6.8), Inches(4.45), ha_w, ha_h,
        "Empirically Tested Chaos Failover",
        [
            "• Automated chaos script (test_ha_failover.sh) verifies resilience.",
            "• Random container kills on Kafka brokers & Flink workers.",
            "• 100% verified message delivery without duplicate commits."
        ],
        COLOR_ACCENT_GREEN,
        icon="🧪"
    )

    add_footer(slide9, 9)

    # =========================================================================
    # SLIDE 10: PERFORMANCE BENCHMARKS & EMPIRICAL PROOF
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    set_background(slide10)
    add_header(
        slide10,
        "Empirical Benchmarks",
        "Battle-Tested Performance Under Extreme Streaming Load",
        "Rigorously validated through continuous fault injection, high-throughput load tests, and concurrency audits.",
        COLOR_ACCENT_CYAN
    )

    # 4 Large Metric Cards
    bm_w = Inches(2.78)
    bm_h = Inches(1.5)
    top_bm = Inches(2.05)

    add_metric_callout(slide10, Inches(0.8), top_bm, bm_w, bm_h, "10,000+", "Events / Second", "Single-node streaming throughput", COLOR_ACCENT_CYAN)
    add_metric_callout(slide10, Inches(3.78), top_bm, bm_w, bm_h, "< 2.8 ms", "End-to-End Latency", "p95 ingestion to validation lag", COLOR_ACCENT_BLUE)
    add_metric_callout(slide10, Inches(6.76), top_bm, bm_w, bm_h, "< 0.4 ms", "Drift Detection Lag", "Zero-I/O in-memory schema check", COLOR_ACCENT_PURPLE)
    add_metric_callout(slide10, Inches(9.74), top_bm, bm_w, bm_h, "0 Lost", "ACID Audit (500 Concurrency)", "Zero lost updates or phantom reads", COLOR_ACCENT_GREEN)

    # Detailed Benchmark Breakdown Table / Cards below
    bench_card_w = Inches(5.7)
    bench_card_h = Inches(2.8)
    top_bcard = Inches(3.85)

    add_card(
        slide10, Inches(0.8), top_bcard, bench_card_w, bench_card_h,
        "Streaming Throughput & In-Flight Latency",
        [
            "• Peak Generator Rate: Sustains 1,000 to 10,000 events/sec with real-time anomaly injection without consumer lag buildup.",
            "• Flink 2PC Latency: Checkpoint barriers flush every 10s with sub-second commit latency to Iceberg REST Catalog.",
            "• Memory Efficiency: Bounded state window aggregators restrict memory overhead to < 120 MB under continuous multi-hour loads."
        ],
        COLOR_ACCENT_CYAN,
        icon="🚀"
    )

    add_card(
        slide10, Inches(6.8), top_bcard, bench_card_w, bench_card_h,
        "ACID Concurrency & Quarantine Stress Test",
        [
            "• Quarantine DLQ Throughput: QuarantineWriter buffers and flushes 1,000 bad records/sec without single-record S3 file explosion.",
            "• 500-Writer Concurrency OCC: Simulated concurrent Iceberg appends achieved 100% commit success via exponential backoff.",
            "• Fast Recovery: Complete autonomous remediation loop finishes in < 30 seconds from circuit trip to clean resume."
        ],
        COLOR_ACCENT_GREEN,
        icon="💎"
    )

    add_footer(slide10, 10)

    # =========================================================================
    # SLIDE 11: POLYGLOT MODERN TECH STACK
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    set_background(slide11)
    add_header(
        slide11,
        "Technology Foundation",
        "Best-of-Breed Polyglot Data Stack",
        "Open-source, cloud-native enterprise components integrated into a cohesive, production-grade ecosystem.",
        COLOR_ACCENT_CYAN
    )

    stack_w = Inches(3.68)
    stack_h = Inches(2.15)

    add_card(
        slide11, Inches(0.8), Inches(2.05), stack_w, stack_h,
        "Streaming & Ingestion",
        [
            "• Apache Kafka (KRaft mode quorum)",
            "• Apache Flink 1.18 (Stream SQL)",
            "• Exactly-Once Two-Phase Commit",
            "• Python High-Throughput Generator"
        ],
        COLOR_ACCENT_BLUE,
        icon="📡"
    )

    add_card(
        slide11, Inches(4.82), Inches(2.05), stack_w, stack_h,
        "Lakehouse & Storage",
        [
            "• Apache Iceberg (Format v2)",
            "• REST Catalog (tabulario/iceberg-rest)",
            "• MinIO S3-Compatible Object Store",
            "• Columnar Apache Parquet"
        ],
        COLOR_ACCENT_CYAN,
        icon="❄"
    )

    add_card(
        slide11, Inches(8.85), Inches(2.05), stack_w, stack_h,
        "Quality & Data Contracts",
        [
            "• Custom 7-Vector Anomaly Engine",
            "• Great Expectations (v0.18.19)",
            "• JSON Schema Evolution Registry",
            "• Rolling-Window Error-Rate Engine"
        ],
        COLOR_ACCENT_PURPLE,
        icon="🛡"
    )

    add_card(
        slide11, Inches(0.8), Inches(4.45), stack_w, stack_h,
        "Backend & Control Plane",
        [
            "• FastAPI (Asynchronous Python 3.10+)",
            "• PostgreSQL (Authoritative state)",
            "• Pydantic v2 Contract Validation",
            "• Bearer Token Authentication"
        ],
        COLOR_ACCENT_GREEN,
        icon="⚡"
    )

    add_card(
        slide11, Inches(4.82), Inches(4.45), stack_w, stack_h,
        "UI & Observability",
        [
            "• React 18 + TypeScript + Vite",
            "• React Flow (@xyflow/react DAG)",
            "• Prometheus Exporter & Metrics",
            "• Grafana Pre-Configured Dashboards"
        ],
        COLOR_ACCENT_AMBER,
        icon="🖥"
    )

    add_card(
        slide11, Inches(8.85), Inches(4.45), stack_w, stack_h,
        "DevOps & Infrastructure",
        [
            "• Docker & Docker Compose HA",
            "• Kubernetes Cloud Manifests",
            "• Slack Webhook Alerts Integration",
            "• 200+ Automated Pytest Test Suite"
        ],
        COLOR_ACCENT_RED,
        icon="🐳"
    )

    add_footer(slide11, 11)

    # =========================================================================
    # SLIDE 12: BUSINESS ROI & SUMMARY
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    set_background(slide12)
    add_header(
        slide12,
        "Executive Summary",
        "Business Impact & The Future of Autonomous Data Platforms",
        "Transforming enterprise data reliability from manual firefighting to continuous, self-healing assurance.",
        COLOR_ACCENT_GREEN
    )

    roi_w = Inches(5.7)
    roi_h = Inches(3.3)
    top_roi = Inches(2.05)

    add_card(
        slide12, Inches(0.8), top_roi, roi_w, roi_h,
        "Before IceStream (Industry Baseline)",
        [
            "✖ Silent data corruption slips into production lakehouse undetected.",
            "✖ Contaminated BI reports lead to bad executive business decisions.",
            "✖ MTTD: 24 to 48 hours; MTTR: 4 to 8 hours of manual engineer intervention.",
            "✖ Engineers waste 30% of engineering bandwidth on backfills and firefighting.",
            "✖ High cloud storage costs from uncontrolled small-file proliferation."
        ],
        COLOR_ACCENT_RED,
        icon="✖"
    )

    add_card(
        slide12, Inches(6.8), top_roi, roi_w, roi_h,
        "With IceStream (Enterprise Advantage)",
        [
            "✔ 100% of event streams verified in real time; 0% silent corruption.",
            "✔ Dynamic circuit breakers protect downstream silver/gold analytics tables.",
            "✔ Autonomous MTTR in < 30 seconds with complete Slack audit trails.",
            "✔ Engineering teams refocus entirely on new business products.",
            "✔ Optimized Iceberg compaction cuts S3 list/read IOPS overhead by 80%."
        ],
        COLOR_ACCENT_GREEN,
        icon="✔"
    )

    # Bottom Call to Action Card
    cta = slide12.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(5.6), Inches(11.733), Inches(1.1)
    )
    cta.fill.solid()
    cta.fill.fore_color.rgb = RGBColor(16, 26, 48)
    cta.line.color.rgb = COLOR_ACCENT_CYAN
    cta.line.width = Pt(1.5)

    tb_cta = slide12.shapes.add_textbox(Inches(1.0), Inches(5.68), Inches(11.333), Inches(0.95))
    tf_cta = tb_cta.text_frame
    tf_cta.word_wrap = True
    p_cta1 = tf_cta.paragraphs[0]
    p_cta1.alignment = PP_ALIGN.CENTER
    p_cta1.text = "READY FOR ENTERPRISE DEPLOYMENT  •  SINGLE-COMMAND START: ./start.sh"
    p_cta1.font.name = FONT_HEADING
    p_cta1.font.size = Pt(14)
    p_cta1.font.bold = True
    p_cta1.font.color.rgb = COLOR_ACCENT_CYAN

    p_cta2 = tf_cta.add_paragraph()
    p_cta2.alignment = PP_ALIGN.CENTER
    p_cta2.text = "React Dashboard: http://localhost:5173  |  FastAPI Telemetry: http://localhost:8000  |  Grafana: http://localhost:3000"
    p_cta2.font.name = FONT_BODY
    p_cta2.font.size = Pt(11)
    p_cta2.font.color.rgb = COLOR_TEXT_MUTED
    p_cta2.space_before = Pt(3)

    add_footer(slide12, 12)

    # Save presentation
    output_path = "/Users/sujal/Desktop/IceStream/IceStream_Presentation.pptx"
    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path}")


if __name__ == "__main__":
    create_presentation()
