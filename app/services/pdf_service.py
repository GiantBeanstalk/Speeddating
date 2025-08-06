"""
PDF Badge Generation Service

Creates PDF badges with QR codes for event attendees.
"""

import uuid
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Attendee, Event

from .qr_service import QRCodeService


class PDFBadgeService:
    """Service for generating PDF badges with QR codes."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.qr_service = QRCodeService(session)

        # Badge configuration from settings
        self.badges_per_page = settings.get("pdf_badges_per_page", 35)
        self.page_size = A4
        self.page_width, self.page_height = self.page_size

        # Calculate badge dimensions for optimal layout
        self._calculate_badge_layout()

    def _calculate_badge_layout(self):
        """Calculate optimal badge layout based on badges per page."""

        # Standard A4 dimensions with margins
        usable_width = self.page_width - (20 * mm)  # 10mm margin on each side
        usable_height = self.page_height - (20 * mm)  # 10mm margin top/bottom

        if self.badges_per_page == 35:
            # 5 columns x 7 rows = 35 badges
            self.cols = 5
            self.rows = 7
        elif self.badges_per_page == 24:
            # 4 columns x 6 rows = 24 badges
            self.cols = 4
            self.rows = 6
        elif self.badges_per_page == 20:
            # 4 columns x 5 rows = 20 badges
            self.cols = 4
            self.rows = 5
        else:
            # Default to 35 badges layout
            self.cols = 5
            self.rows = 7

        self.badge_width = usable_width / self.cols
        self.badge_height = usable_height / self.rows

        # QR code size (should fit within badge with some padding)
        self.qr_size = min(self.badge_width * 0.4, self.badge_height * 0.4)

    async def generate_event_badges(
        self, event_id: uuid.UUID, include_qr: bool = True, font_size: int = 8
    ) -> BytesIO:
        """Generate PDF badges for all attendees of an event."""

        # Get event and attendees
        event_result = await self.session.execute(
            select(Event)
            .options(selectinload(Event.attendees))
            .where(Event.id == event_id)
        )
        event = event_result.scalar_one_or_none()

        if not event:
            raise ValueError("Event not found")

        # Filter confirmed attendees
        attendees = [a for a in event.attendees if a.registration_confirmed]

        if not attendees:
            raise ValueError("No confirmed attendees found")

        # Generate QR tokens if requested (profile QR codes for badges)
        qr_data = {}
        if include_qr:
            for attendee in attendees:
                try:
                    # Generate profile QR token for public profile access
                    from app.models.qr_login import QRLogin

                    qr_login = QRLogin.create_for_attendee(
                        attendee_id=attendee.id,
                        event_id=event_id,
                        user_id=attendee.user_id,
                        expire_hours=168,  # 7 days for profile badges
                        token_type="profile_view",
                    )

                    # Set QR URL for profile viewing
                    from app.config import settings

                    base_url = settings.get("qr_code_base_url", "http://localhost:8000")
                    qr_login.qr_code_url = (
                        f"{base_url}/profiles/{attendee.id}?qr_token={qr_login.token}"
                    )

                    # Generate the attendee's profile QR token if not exists
                    if not attendee.profile_qr_token:
                        attendee.generate_profile_qr_token()

                    qr_data[attendee.id] = qr_login
                    self.session.add(qr_login)

                except Exception as e:
                    print(
                        f"Failed to generate profile QR for attendee {attendee.id}: {e}"
                    )

            # Commit QR tokens to database
            await self.session.commit()

        # Create PDF
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=self.page_size)

        # Set up styles
        styles = getSampleStyleSheet()
        name_style = ParagraphStyle(
            "BadgeName",
            parent=styles["Normal"],
            fontSize=font_size + 2,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            textColor=colors.black,
        )

        info_style = ParagraphStyle(
            "BadgeInfo",
            parent=styles["Normal"],
            fontSize=font_size,
            alignment=TA_CENTER,
            fontName="Helvetica",
            textColor=colors.black,
        )

        # Generate badges
        badges_created = 0

        for i, attendee in enumerate(attendees):
            # Calculate position on current page
            page_position = i % self.badges_per_page
            col = page_position % self.cols
            row = page_position // self.cols

            # Start new page if needed
            if i > 0 and page_position == 0:
                c.showPage()

            # Calculate badge position
            x = 10 * mm + (col * self.badge_width)
            y = self.page_height - 10 * mm - ((row + 1) * self.badge_height)

            # Draw badge
            self._draw_single_badge(
                c,
                attendee,
                event,
                x,
                y,
                qr_data.get(attendee.id),
                name_style,
                info_style,
            )

            badges_created += 1

        # Add metadata
        c.setCreator("Speed Dating App")
        c.setTitle(f"Badges for {event.name}")
        c.setSubject(
            f"Event badges generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        c.save()
        pdf_buffer.seek(0)

        return pdf_buffer

    def _draw_single_badge(
        self,
        canvas_obj: canvas.Canvas,
        attendee: Attendee,
        event: Event,
        x: float,
        y: float,
        qr_login: Any | None,
        name_style: ParagraphStyle,
        info_style: ParagraphStyle,
    ):
        """Draw a single badge on the canvas."""

        # Draw badge border
        canvas_obj.setStrokeColor(colors.black)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.rect(x, y, self.badge_width, self.badge_height)

        # Content area with padding
        content_x = x + 2 * mm
        content_y = y + 2 * mm
        content_width = self.badge_width - 4 * mm
        content_height = self.badge_height - 4 * mm

        # Draw QR code if available (for profile viewing)
        qr_y_offset = 0
        if qr_login:
            qr_img = self.qr_service.create_qr_code_image(
                qr_login.qr_code_url, size=3, border=1
            )

            # Position QR code at top-right of badge
            qr_x = content_x + content_width - self.qr_size
            qr_y = content_y + content_height - self.qr_size

            canvas_obj.drawInlineImage(
                qr_img, qr_x, qr_y, width=self.qr_size, height=self.qr_size
            )

            # Add "Profile" label under QR code
            canvas_obj.setFont("Helvetica", 6)
            canvas_obj.setFillColor(colors.black)
            canvas_obj.drawCentredText(
                qr_x + (self.qr_size / 2), qr_y - 3 * mm, "Profile"
            )

            qr_y_offset = self.qr_size + 5 * mm  # Extra space for label

        # Draw attendee name
        name_text = attendee.display_name or "Attendee"
        name_frame = Frame(
            content_x,
            content_y + content_height - 15 * mm - qr_y_offset,
            content_width - (self.qr_size + 2 * mm if qr_login else 0),
            10 * mm,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )

        name_para = Paragraph(name_text, name_style)
        name_frame.addFromList([name_para], canvas_obj)

        # Draw category
        category_text = attendee.category.value.replace("_", " ").title()
        category_frame = Frame(
            content_x,
            content_y + content_height - 25 * mm - qr_y_offset,
            content_width - (self.qr_size + 2 * mm if qr_login else 0),
            8 * mm,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )

        category_para = Paragraph(f"<b>{category_text}</b>", info_style)
        category_frame.addFromList([category_para], canvas_obj)

        # Draw event name
        event_text = event.name
        if len(event_text) > 30:  # Truncate long event names
            event_text = event_text[:27] + "..."

        event_frame = Frame(
            content_x,
            content_y + content_height - 35 * mm - qr_y_offset,
            content_width - (self.qr_size + 2 * mm if qr_login else 0),
            8 * mm,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )

        event_para = Paragraph(event_text, info_style)
        event_frame.addFromList([event_para], canvas_obj)

        # Draw event date
        event_date = event.event_date.strftime("%B %d, %Y")
        date_frame = Frame(
            content_x,
            content_y + 2 * mm,
            content_width,
            6 * mm,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )

        date_para = Paragraph(event_date, info_style)
        date_frame.addFromList([date_para], canvas_obj)

        # Draw attendee ID (small text at bottom)
        canvas_obj.setFont("Helvetica", 6)
        canvas_obj.setFillColor(colors.grey)
        id_text = f"ID: {str(attendee.id)[:8]}"
        canvas_obj.drawString(content_x, content_y - 1 * mm, id_text)
        canvas_obj.setFillColor(colors.black)  # Reset color

    async def generate_single_badge(
        self, attendee_id: uuid.UUID, include_qr: bool = True
    ) -> BytesIO:
        """Generate a PDF badge for a single attendee."""

        # Get attendee with event
        attendee_result = await self.session.execute(
            select(Attendee)
            .options(selectinload(Attendee.event))
            .where(Attendee.id == attendee_id)
        )
        attendee = attendee_result.scalar_one_or_none()

        if not attendee:
            raise ValueError("Attendee not found")

        # Generate QR token if requested
        qr_login = None
        if include_qr:
            qr_login = await self.qr_service.generate_attendee_qr_token(attendee_id)

        # Create PDF with single badge centered on page
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=self.page_size)

        # Center the badge on the page
        badge_x = (self.page_width - self.badge_width) / 2
        badge_y = (self.page_height - self.badge_height) / 2

        # Set up styles
        styles = getSampleStyleSheet()
        name_style = ParagraphStyle(
            "BadgeName",
            parent=styles["Normal"],
            fontSize=14,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )

        info_style = ParagraphStyle(
            "BadgeInfo",
            parent=styles["Normal"],
            fontSize=10,
            alignment=TA_CENTER,
            fontName="Helvetica",
        )

        # Draw the badge
        self._draw_single_badge(
            c,
            attendee,
            attendee.event,
            badge_x,
            badge_y,
            qr_login,
            name_style,
            info_style,
        )

        c.setCreator("Speed Dating App")
        c.setTitle(f"Badge for {attendee.display_name}")
        c.save()

        pdf_buffer.seek(0)
        return pdf_buffer

    async def get_badge_generation_stats(self, event_id: uuid.UUID) -> dict[str, Any]:
        """Get statistics about badge generation for an event."""

        # Get attendee counts
        attendees_result = await self.session.execute(
            select(Attendee).where(Attendee.event_id == event_id)
        )
        attendees = list(attendees_result.scalars())

        confirmed_attendees = [a for a in attendees if a.registration_confirmed]

        # Calculate pages needed
        pages_needed = (
            len(confirmed_attendees) + self.badges_per_page - 1
        ) // self.badges_per_page

        return {
            "total_attendees": len(attendees),
            "confirmed_attendees": len(confirmed_attendees),
            "badges_per_page": self.badges_per_page,
            "pages_needed": pages_needed,
            "layout": f"{self.cols}x{self.rows}",
            "badge_size_mm": {
                "width": round(self.badge_width / mm, 1),
                "height": round(self.badge_height / mm, 1),
            },
        }


async def create_pdf_service(session: AsyncSession) -> PDFBadgeService:
    """Factory function to create a PDFBadgeService instance."""
    return PDFBadgeService(session)
