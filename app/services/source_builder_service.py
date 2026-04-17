from __future__ import annotations

from pathlib import Path

from app.models.sources import TextSourceInput


class SourceBuilderService:
    def normalize_single(self, title: str, content: str) -> TextSourceInput:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title:
            raise ValueError("title nao pode ser vazio")
        if not clean_content:
            raise ValueError("content nao pode ser vazio")
        return TextSourceInput(title=clean_title, content=clean_content)

    def normalize_batch(self, sources: list[TextSourceInput]) -> list[TextSourceInput]:
        normalized: list[TextSourceInput] = []
        for source in sources:
            item = self.normalize_single(source.title, source.content)
            normalized.append(item)
        return normalized

    def write_temp_sources(
        self,
        job_id: str,
        temp_root: Path,
        sources: list[TextSourceInput],
    ) -> list[Path]:
        target_dir = temp_root / job_id
        target_dir.mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []
        for index, source in enumerate(sources, start=1):
            file_path = target_dir / f"source_{index:02d}.md"
            file_path.write_text(f"# {source.title}\n\n{source.content}\n", encoding="utf-8")
            created_files.append(file_path)
        return created_files
