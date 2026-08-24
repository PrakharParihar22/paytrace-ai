from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BRAND = colors.HexColor("#635BFF")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#667085")
BORDER = colors.HexColor("#E4E7EC")
PANEL = colors.HexColor("#F8FAFC")
SUCCESS = colors.HexColor("#067647")
SUCCESS_BG = colors.HexColor("#ECFDF3")
DANGER = colors.HexColor("#B42318")
DANGER_BG = colors.HexColor("#FEF3F2")
WARNING = colors.HexColor("#B54708")
WARNING_BG = colors.HexColor("#FFFAEB")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape(value: Any) -> str:
    if value is None:
        return "-"

    text = str(value)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _money(amount_paise: Any, currency: str | None = "INR") -> str:
    if amount_paise is None:
        return "-"

    try:
        amount = float(amount_paise) / 100.0
    except (TypeError, ValueError):
        return str(amount_paise)

    return f"{currency or 'INR'} {amount:,.2f}"


def _status_style(status: str | None):
    normalized = (status or "").upper()

    if normalized in {
        "PASS",
        "PAID",
        "HEALTHY",
        "RECOVERED",
        "REPRODUCED",
        "VERIFIED",
        "CONFIRMED",
        "FIX_VERIFIED",
    }:
        return SUCCESS, SUCCESS_BG

    if normalized in {
        "FAIL",
        "FAILED",
        "INVESTIGATED",
        "INCIDENT",
        "ACTIVE",
        "NOT_VERIFIED",
        "FIX_NOT_VERIFIED",
    }:
        return DANGER, DANGER_BG

    return WARNING, WARNING_BG


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="PayTraceTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=INK,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="PayTraceSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=MUTED,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=INK,
            spaceBefore=4,
            spaceAfter=7,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Kicker",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            tracking=1.2,
            textColor=BRAND,
            spaceAfter=3,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#344054"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyTiny",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.5,
            textColor=colors.HexColor("#475467"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="MonoTiny",
            parent=styles["BodyText"],
            fontName="Courier",
            fontSize=6.8,
            leading=9,
            textColor=colors.HexColor("#344054"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="BigStatus",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=INK,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CenterTiny",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=MUTED,
        )
    )

    return styles


def _header_footer(canvas, doc):
    canvas.saveState()

    width, height = A4

    canvas.setFillColor(colors.HexColor("#0B1020"))
    canvas.rect(
        0,
        height - 17 * mm,
        width,
        17 * mm,
        stroke=0,
        fill=1,
    )

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(
        doc.leftMargin,
        height - 10.5 * mm,
        "PAYTRACE",
    )

    canvas.setFillColor(colors.HexColor("#B7BCE8"))
    canvas.setFont("Helvetica", 6.5)
    canvas.drawRightString(
        width - doc.rightMargin,
        height - 10.5 * mm,
        "PAYMENT RELIABILITY INCIDENT REPORT",
    )

    canvas.setStrokeColor(BORDER)
    canvas.line(
        doc.leftMargin,
        12 * mm,
        width - doc.rightMargin,
        12 * mm,
    )

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(
        doc.leftMargin,
        7.5 * mm,
        "Generated from PayTrace / Razorpay Test Mode evidence",
    )

    canvas.drawRightString(
        width - doc.rightMargin,
        7.5 * mm,
        f"Page {doc.page}",
    )

    canvas.restoreState()


def _section_heading(story, styles, kicker: str, title: str):
    story.append(
        Paragraph(
            _escape(kicker.upper()),
            styles["Kicker"],
        )
    )
    story.append(
        Paragraph(
            _escape(title),
            styles["SectionTitle"],
        )
    )


def _kv_table(styles, rows: list[tuple[str, Any]], widths=None):
    data = []

    for label, value in rows:
        data.append(
            [
                Paragraph(
                    f"<b>{_escape(label)}</b>",
                    styles["BodyTiny"],
                ),
                Paragraph(
                    _escape(value),
                    styles["BodyTiny"],
                ),
            ]
        )

    table = Table(
        data,
        colWidths=widths or [43 * mm, 125 * mm],
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def _status_box(styles, label: str, status: str):
    fg, bg = _status_style(status)

    box = Table(
        [
            [
                Paragraph(
                    f"<b>{_escape(label)}</b>",
                    styles["BodyTiny"],
                ),
                Paragraph(
                    f"<b>{_escape(status)}</b>",
                    styles["BodyTiny"],
                ),
            ]
        ],
        colWidths=[67 * mm, 101 * mm],
    )

    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PANEL),
                ("BACKGROUND", (1, 0), (1, 0), bg),
                ("TEXTCOLOR", (1, 0), (1, 0), fg),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    return box


def _latest_matching_complaint(order_id: str):
    try:
        from app.agents.complaint_intake import get_recent_complaints

        complaints = get_recent_complaints(100)
    except Exception:
        return None

    for complaint in complaints:
        matched = (
            complaint.get("correlation", {})
            .get("matched_order")
        )

        if matched and matched.get("order_id") == order_id:
            return complaint

    return None


def _latest_reliability_run():
    try:
        from app.services.reliability_service import (
            get_latest_reliability_suite,
        )

        return get_latest_reliability_suite()
    except Exception:
        return None


def generate_incident_report_pdf(order_id: str) -> bytes | None:
    from app.services.dashboard_service import build_order_report

    report = build_order_report(order_id)

    if not report:
        return None

    complaint = _latest_matching_complaint(order_id)
    reliability = _latest_reliability_run()

    return build_incident_pdf(
        report=report,
        complaint=complaint,
        reliability=reliability,
        generated_at=_now_iso(),
    )


def build_incident_pdf(
    report: dict,
    complaint: dict | None = None,
    reliability: dict | None = None,
    generated_at: str | None = None,
) -> bytes:
    styles = _build_styles()

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=21 * mm,
        rightMargin=21 * mm,
        topMargin=24 * mm,
        bottomMargin=18 * mm,
        title=(
            f"PayTrace Incident Report - "
            f"{report.get('order', {}).get('id', 'Unknown')}"
        ),
        author="PayTrace AI",
        subject="Payment reliability incident investigation",
    )

    story = []

    order = report.get("order", {}) or {}
    analysis = report.get("analysis", {}) or {}
    investigation = report.get("investigation", {}) or {}
    primary = investigation.get("primary_hypothesis") or {}
    fix_wrapper = report.get("fix", {}) or {}
    fix = fix_wrapper.get("fix") or {}
    timeline_wrapper = report.get("timeline", {}) or {}
    timeline = timeline_wrapper.get("timeline", []) or []
    reproduction = report.get("latest_reproduction") or {}
    regression = report.get("latest_regression") or {}

    order_id = order.get("id", "-")
    payment_id = order.get("payment_id", "-")
    incident_status = investigation.get("status", "UNKNOWN")
    root_cause = primary.get("code") or "No active root cause"
    confidence = primary.get("confidence")
    confidence_text = (
        f"{round(confidence * 100)}%"
        if isinstance(confidence, (int, float))
        else "-"
    )

    # Cover / summary
    story.append(
        Paragraph(
            "PayTrace Incident Report",
            styles["PayTraceTitle"],
        )
    )

    story.append(
        Paragraph(
            (
                "Deterministic payment evidence, root-cause analysis, "
                "reproduction proof and regression verification."
            ),
            styles["PayTraceSubtitle"],
        )
    )

    story.append(Spacer(1, 5 * mm))

    story.append(
        _status_box(
            styles,
            "Incident status",
            incident_status,
        )
    )

    story.append(Spacer(1, 3 * mm))

    story.append(
        _kv_table(
            styles,
            [
                ("Order ID", order_id),
                ("Payment ID", payment_id),
                (
                    "Amount",
                    _money(
                        order.get("amount"),
                        order.get("currency"),
                    ),
                ),
                (
                    "Merchant state",
                    order.get("merchant_state", "-"),
                ),
                (
                    "Root cause",
                    root_cause,
                ),
                (
                    "Root-cause confidence",
                    confidence_text,
                ),
                (
                    "Failure boundary",
                    primary.get(
                        "failure_boundary",
                        "-",
                    ),
                ),
                (
                    "Generated at",
                    generated_at or _now_iso(),
                ),
            ],
        )
    )

    story.append(Spacer(1, 5 * mm))

    _section_heading(
        story,
        styles,
        "Executive summary",
        "What PayTrace concluded",
    )

    summary_text = primary.get("reason")

    if not summary_text:
        if incident_status == "HEALTHY":
            summary_text = (
                "Provider and merchant payment states are currently "
                "consistent. No active root-cause hypothesis is required."
            )
        else:
            summary_text = (
                "PayTrace reconstructed the available payment timeline "
                "and evaluated provider and merchant state consistency."
            )

    story.append(
        Paragraph(
            _escape(summary_text),
            styles["BodySmall"],
        )
    )

    # Complaint
    if complaint:
        story.append(Spacer(1, 5 * mm))
        _section_heading(
            story,
            styles,
            "Reported symptom",
            "Complaint correlated with this order",
        )

        correlation = complaint.get("correlation", {}) or {}

        story.append(
            _kv_table(
                styles,
                [
                    (
                        "Complaint ID",
                        complaint.get("complaint_id", "-"),
                    ),
                    (
                        "Reported issue type",
                        complaint.get(
                            "reported_issue_type",
                            "-",
                        ),
                    ),
                    (
                        "Correlation status",
                        correlation.get("status", "-"),
                    ),
                    (
                        "Correlation basis",
                        correlation.get("basis", "-"),
                    ),
                    (
                        "Match confidence",
                        (
                            f"{round((correlation.get('confidence_score') or 0) * 100)}%"
                        ),
                    ),
                ],
            )
        )

        story.append(Spacer(1, 2 * mm))

        story.append(
            Paragraph(
                f"<b>Complaint:</b> {_escape(complaint.get('message', '-'))}",
                styles["BodySmall"],
            )
        )

    # System truth
    story.append(Spacer(1, 5 * mm))
    _section_heading(
        story,
        styles,
        "System truth",
        "Provider and merchant state",
    )

    provider_state = analysis.get("provider_state", {}) or {}

    story.append(
        _kv_table(
            styles,
            [
                (
                    "Provider payment captured",
                    str(
                        bool(
                            provider_state.get(
                                "payment_captured"
                            )
                        )
                    ).upper(),
                ),
                (
                    "Provider order paid",
                    str(
                        bool(
                            provider_state.get(
                                "order_paid"
                            )
                        )
                    ).upper(),
                ),
                (
                    "Merchant state",
                    order.get("merchant_state", "-"),
                ),
                (
                    "State divergence active",
                    str(
                        bool(
                            analysis.get(
                                "state_divergence"
                            )
                        )
                    ).upper(),
                ),
            ],
        )
    )

    # Root cause and evidence
    root_block = []

    _section_heading(
        root_block,
        styles,
        "Root cause",
        root_cause,
    )

    root_block.append(
        _kv_table(
            styles,
            [
                ("Confidence", confidence_text),
                (
                    "Failure boundary",
                    primary.get(
                        "failure_boundary",
                        "-",
                    ),
                ),
                (
                    "Incident phase",
                    primary.get(
                        "incident_phase",
                        (
                            "RECOVERED"
                            if incident_status == "RECOVERED"
                            else "ACTIVE"
                        ),
                    ),
                ),
            ],
        )
    )

    supporting = primary.get("supporting_evidence", []) or []

    if supporting:
        root_block.append(Spacer(1, 2 * mm))

        for item in supporting:
            root_block.append(
                Paragraph(
                    f"- {_escape(item)}",
                    styles["BodySmall"],
                )
            )

    # Keep the root-cause title with its facts so a page does not end with
    # an orphaned heading.
    story.append(
        KeepTogether(root_block)
    )

    # Timeline
    story.append(Spacer(1, 6 * mm))

    _section_heading(
        story,
        styles,
        "Evidence timeline",
        "Chronology of recorded events",
    )

    max_events = 32
    visible_timeline = timeline[-max_events:]

    if len(timeline) > max_events:
        story.append(
            Paragraph(
                (
                    f"Showing the latest {max_events} of {len(timeline)} "
                    "recorded events."
                ),
                styles["BodyTiny"],
            )
        )
        story.append(Spacer(1, 2 * mm))

    timeline_data = [
        [
            Paragraph("<b>#</b>", styles["BodyTiny"]),
            Paragraph("<b>Event</b>", styles["BodyTiny"]),
            Paragraph("<b>Source</b>", styles["BodyTiny"]),
            Paragraph("<b>Status</b>", styles["BodyTiny"]),
            Paragraph("<b>Message</b>", styles["BodyTiny"]),
        ]
    ]

    for event in visible_timeline:
        timeline_data.append(
            [
                Paragraph(
                    _escape(event.get("sequence", "-")),
                    styles["BodyTiny"],
                ),
                Paragraph(
                    _escape(event.get("type", "-")),
                    styles["MonoTiny"],
                ),
                Paragraph(
                    _escape(event.get("source", "-")),
                    styles["BodyTiny"],
                ),
                Paragraph(
                    _escape(event.get("status", "-")),
                    styles["BodyTiny"],
                ),
                Paragraph(
                    _escape(event.get("message", "-")),
                    styles["BodyTiny"],
                ),
            ]
        )

    timeline_table = Table(
        timeline_data,
        colWidths=[
            8 * mm,
            35 * mm,
            34 * mm,
            23 * mm,
            68 * mm,
        ],
        repeatRows=1,
    )

    timeline_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story.append(timeline_table)

    # Reproduction
    story.append(Spacer(1, 6 * mm))

    _section_heading(
        story,
        styles,
        "Reproduction",
        "Was the suspected failure reproduced?",
    )

    repro_meta = reproduction.get("metadata", {}) or {}
    repro_status = reproduction.get("status") or "NOT_RUN"
    hypothesis_status = (
        repro_meta.get("hypothesis_status")
        or "NOT_TESTED"
    )

    story.append(
        _status_box(
            styles,
            "Reproduction result",
            repro_status,
        )
    )

    story.append(Spacer(1, 2 * mm))

    story.append(
        _kv_table(
            styles,
            [
                (
                    "Hypothesis",
                    repro_meta.get(
                        "hypothesis",
                        root_cause,
                    ),
                ),
                (
                    "Hypothesis status",
                    hypothesis_status,
                ),
                (
                    "Incident phase",
                    repro_meta.get(
                        "incident_phase",
                        "-",
                    ),
                ),
            ],
        )
    )

    expected_signature = repro_meta.get(
        "expected_signature"
    ) or repro_meta.get(
        "original_incident_signature"
    )

    reproduced_signature = repro_meta.get(
        "reproduced_signature"
    )

    if expected_signature or reproduced_signature:
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                (
                    "<b>Failure signature comparison:</b><br/>"
                    f"Expected: {_escape(expected_signature)}<br/>"
                    f"Reproduced: {_escape(reproduced_signature)}"
                ),
                styles["MonoTiny"],
            )
        )

    # Fix
    story.append(Spacer(1, 6 * mm))

    _section_heading(
        story,
        styles,
        "Fix direction",
        fix.get(
            "title",
            "No verified fix direction available",
        ),
    )

    if fix:
        story.append(
            Paragraph(
                _escape(
                    fix.get(
                        "summary",
                        "-",
                    )
                ),
                styles["BodySmall"],
            )
        )

        changes = fix.get("changes", []) or []

        if changes:
            story.append(Spacer(1, 2 * mm))

            for change in changes:
                story.append(
                    KeepTogether(
                        [
                            Paragraph(
                                (
                                    f"<b>{_escape(change.get('priority', '-'))}. "
                                    f"{_escape(change.get('change', '-'))}</b>"
                                ),
                                styles["BodySmall"],
                            ),
                            Paragraph(
                                _escape(
                                    change.get(
                                        "why",
                                        "",
                                    )
                                ),
                                styles["BodyTiny"],
                            ),
                            Spacer(1, 1.5 * mm),
                        ]
                    )
                )

    # Regression
    story.append(Spacer(1, 5 * mm))

    _section_heading(
        story,
        styles,
        "Regression verification",
        "Did the same scenario pass after the proposed fix?",
    )

    reg_meta = regression.get("metadata", {}) or {}
    reg_status = regression.get("status") or "NOT_RUN"
    fix_status = reg_meta.get("fix_status") or "NOT_VERIFIED"

    story.append(
        _status_box(
            styles,
            "Regression result",
            reg_status,
        )
    )

    story.append(Spacer(1, 2 * mm))

    story.append(
        _status_box(
            styles,
            "Fix status",
            fix_status,
        )
    )

    before = reg_meta.get("before")
    after = reg_meta.get("after")

    if before or after:
        story.append(Spacer(1, 2 * mm))

        comparison = Table(
            [
                [
                    Paragraph(
                        "<b>Signal</b>",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        "<b>Before fix</b>",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        "<b>After fix</b>",
                        styles["BodyTiny"],
                    ),
                ],
                [
                    Paragraph(
                        "Provider paid",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (before or {}).get(
                                "provider_paid",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (after or {}).get(
                                "provider_paid",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                ],
                [
                    Paragraph(
                        "Webhook processing failed",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (before or {}).get(
                                "webhook_processing_failed",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (after or {}).get(
                                "webhook_processing_failed",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                ],
                [
                    Paragraph(
                        "Merchant paid",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (before or {}).get(
                                "merchant_paid",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (after or {}).get(
                                "merchant_paid",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                ],
                [
                    Paragraph(
                        "State divergence",
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (before or {}).get(
                                "state_divergence",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                    Paragraph(
                        _escape(
                            (after or {}).get(
                                "state_divergence",
                                "-",
                            )
                        ),
                        styles["BodyTiny"],
                    ),
                ],
            ],
            colWidths=[
                68 * mm,
                50 * mm,
                50 * mm,
            ],
        )

        comparison.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                    ("BOX", (0, 0), (-1, -1), 0.45, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        story.append(Spacer(1, 2 * mm))
        story.append(comparison)

    # Reliability
    story.append(Spacer(1, 6 * mm))

    _section_heading(
        story,
        styles,
        "Reliability context",
        "Current executable PayTrace reliability suite",
    )

    if reliability:
        score = reliability.get("score")
        passed = reliability.get("passed", 0)
        total = reliability.get("total", 0)

        story.append(
            _kv_table(
                styles,
                [
                    (
                        "Reliability score",
                        (
                            f"{score}/100"
                            if score is not None
                            else "-"
                        ),
                    ),
                    (
                        "Scenarios passed",
                        f"{passed}/{total}",
                    ),
                    (
                        "Execution mode",
                        reliability.get(
                            "execution_mode",
                            "-",
                        ),
                    ),
                    (
                        "Last run",
                        reliability.get(
                            "executed_at",
                            "-",
                        ),
                    ),
                ],
            )
        )

        story.append(Spacer(1, 2 * mm))

        story.append(
            Paragraph(
                (
                    "Interpretation: this score measures the percentage "
                    "of PayTrace's current executable reliability scenarios "
                    "whose defined assertions passed. It is not a claim of "
                    "100% production reliability."
                ),
                styles["BodyTiny"],
            )
        )

    else:
        story.append(
            Paragraph(
                "No reliability-suite run was available at export time.",
                styles["BodySmall"],
            )
        )

    # Safety / audit
    story.append(Spacer(1, 6 * mm))

    _section_heading(
        story,
        styles,
        "Safety and audit statement",
        "Bounded execution",
    )

    story.append(
        Paragraph(
            (
                "This report was generated from PayTrace evidence in "
                "Razorpay Test Mode. Reproduction and regression checks "
                "operate inside the isolated PayTrace reliability lab. "
                "PayTrace does not automatically modify production code, "
                "move real money, contact customers, or initiate refunds "
                "or charges."
            ),
            styles["BodySmall"],
        )
    )

    story.append(Spacer(1, 4 * mm))
    story.append(
        HRFlowable(
            width="100%",
            thickness=0.5,
            color=BORDER,
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            (
                f"Report order: {_escape(order_id)} | "
                f"Payment: {_escape(payment_id)} | "
                f"PayTrace incident status: {_escape(incident_status)}"
            ),
            styles["CenterTiny"],
        )
    )

    doc.build(
        story,
        onFirstPage=_header_footer,
        onLaterPages=_header_footer,
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
