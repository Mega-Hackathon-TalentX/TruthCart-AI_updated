import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.config import settings
from app.core.logging_config import SafeLogger

class PolicySection:
    def __init__(self, section_id: str, title: str, content: str, topic: str):
        self.section_id = section_id.strip() # e.g. "POLICY:RETURNS"
        self.title = title.strip()
        self.content = content.strip()
        self.topic = topic.strip().upper() # "RETURNS", "SHIPPING", "WARRANTY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "topic": self.topic
        }

class PolicyLoader:
    """Ingests, parses, and indexes the official store policy document."""

    def __init__(self):
        self.sections: Dict[str, PolicySection] = {}
        self.is_official: bool = False
        self.is_synthetic_fixture: bool = False
        self.is_ready: bool = False
        self.source_path: Optional[str] = None

    def clear(self) -> None:
        self.sections.clear()
        self.is_official = False
        self.is_synthetic_fixture = False
        self.is_ready = False
        self.source_path = None

    def parse_text(self, text: str, is_official: bool, is_synthetic: bool, source_name: str) -> None:
        """Parses structured sections with headers into traceable PolicySection objects."""
        self.clear()
        self.is_official = is_official
        self.is_synthetic_fixture = is_synthetic
        self.source_path = source_name

        if not text.strip():
            self.is_ready = False
            return

        # Pattern 1: Section delimiters like '=== SECTION: RETURNS ==='
        section_blocks = re.split(r'={3,}\s*SECTION:\s*([A-Za-z0-9_\s-]+?)\s*={3,}', text, flags=re.IGNORECASE)

        if len(section_blocks) > 1:
            # First element is preamble before first section (if any)
            for i in range(1, len(section_blocks), 2):
                topic = section_blocks[i].strip().upper()
                block_content = section_blocks[i + 1].strip()

                title_match = re.search(r'Title:\s*(.+)', block_content, flags=re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else f"{topic.title()} Policy"

                id_match = re.search(r'Policy ID:\s*(.+)', block_content, flags=re.IGNORECASE)
                section_id = id_match.group(1).strip() if id_match else f"POLICY:{topic}"

                content_match = re.search(r'Content:\s*(.*)', block_content, flags=re.DOTALL | re.IGNORECASE)
                body = content_match.group(1).strip() if content_match else block_content

                section = PolicySection(section_id=section_id, title=title, content=body, topic=topic)
                self.sections[section.section_id] = section
        else:
            # Fallback Pattern 2: Markdown headers '# Return Policy', '## Shipping'
            chunks = re.split(r'\n(?=#{1,3}\s+)', text)
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue
                header_line = chunk.split('\n')[0]
                header_text = re.sub(r'^#{1,3}\s*', '', header_line).strip()
                body = '\n'.join(chunk.split('\n')[1:]).strip()

                topic = "GENERAL"
                lower_h = header_text.lower()
                if "return" in lower_h or "exchange" in lower_h or "refund" in lower_h:
                    topic = "RETURNS"
                elif "ship" in lower_h or "deliver" in lower_h:
                    topic = "SHIPPING"
                elif "warrant" in lower_h or "guarantee" in lower_h:
                    topic = "WARRANTY"

                section_id = f"POLICY:{topic}"
                section = PolicySection(
                    section_id=section_id,
                    title=header_text,
                    content=body if body else header_text,
                    topic=topic
                )
                self.sections[section_id] = section

        self.is_ready = len(self.sections) > 0
        SafeLogger.info(f"Policy parsed from {source_name}: {len(self.sections)} sections loaded.")

    def load_file(self, file_path: Path, is_official: bool = False, is_synthetic: bool = False) -> None:
        if not file_path.exists():
            SafeLogger.warning(f"Policy file not found: {file_path}")
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.parse_text(content, is_official=is_official, is_synthetic=is_synthetic, source_name=file_path.name)
        except Exception as e:
            SafeLogger.error(f"Error loading policy file {file_path.name}: {str(e)}")

    def load_default_policy(self, force_fixtures: bool = False) -> None:
        """Loads official store policy if present, otherwise checks fixture policy if configured."""
        if force_fixtures:
            dev_file = settings.get_dev_fixtures_path() / "sample_policy.txt"
            if dev_file.exists():
                SafeLogger.info("Loading isolated synthetic development policy fixture (forced).")
                self.load_file(dev_file, is_official=False, is_synthetic=True)
                return

        if not force_fixtures:
            try:
                from app.db.database import db
                db.init_db()
                active_pol = db.get_active_policy()
                if active_pol:
                    SafeLogger.info(f"Loading active policy from database: {active_pol['title']} ({active_pol['version']})")
                    self.load_from_database()
                    return
            except Exception as e:
                SafeLogger.warning(f"Could not load policy from database: {str(e)}")

        official_dir = settings.get_policies_path()
        official_files = []
        if official_dir.exists():
            for ext in ("*.txt", "*.md"):
                for p in official_dir.glob(ext):
                    if not p.name.lower().startswith("readme") and not p.name.startswith("."):
                        official_files.append(p)

        if official_files:
            target_file = official_files[0]
            SafeLogger.info(f"Official organiser policy detected: {target_file.name}")
            self.load_file(target_file, is_official=True, is_synthetic=False)
            return

        if settings.LOAD_SYNTHETIC_DEV_DATA_WHEN_EMPTY:
            dev_file = settings.get_dev_fixtures_path() / "sample_policy.txt"
            if dev_file.exists():
                SafeLogger.info("Loading isolated synthetic development policy fixture.")
                self.load_file(dev_file, is_official=False, is_synthetic=True)
                return

        self.clear()
        SafeLogger.info("Official policy document not yet provided. System in 'Awaiting organiser policy' status.")

    def load_from_database(self) -> None:
        """Loads active policy document directly from database."""
        from app.db.database import db
        active_pol = db.get_active_policy()
        if not active_pol:
            self.clear()
            return

        self.parse_text(
            text=active_pol["content"],
            is_official=True,
            is_synthetic=False,
            source_name=f"{active_pol['title']} ({active_pol['version']})"
        )

    def get_section_by_id(self, section_id: str) -> Optional[PolicySection]:
        if not self.is_ready:
            self.load_from_database()
        sid = section_id.strip()
        if sid in self.sections:
            return self.sections[sid]
        clean = sid.replace("POLICY:", "").strip()
        if clean in self.sections:
            return self.sections[clean]
        prefixed = f"POLICY:{sid}"
        if prefixed in self.sections:
            return self.sections[prefixed]
        return self.get_section_by_topic(clean)

    def get_section_by_topic(self, topic: str) -> Optional[PolicySection]:
        if not self.is_ready:
            self.load_from_database()
        topic_upper = topic.strip().upper()
        for s in self.sections.values():
            if s.topic == topic_upper:
                return s
        return None

    def get_all_sections(self) -> List[PolicySection]:
        if not self.is_ready:
            self.load_from_database()
        return list(self.sections.values())


    def get_status(self) -> Dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "is_official": self.is_official,
            "is_synthetic_fixture": self.is_synthetic_fixture,
            "sections_count": len(self.sections),
            "topics": [s.topic for s in self.sections.values()],
            "source_path": self.source_path
        }

policy_loader = PolicyLoader()
